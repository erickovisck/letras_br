import logging
import re
import json
import difflib
import unicodedata
import urllib.parse
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
import httpx
from bs4 import BeautifulSoup

from .languages import DEFAULT_LANGUAGE, LANGUAGES, normalize_lang
from .text_utils import to_romaji

logger = logging.getLogger(__name__)

BASE_URL = "https://www.letras.mus.br"
HEADERS = {
    "User-Agent": "Letras/3.14.0 (Android; 14; Mobile)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
}

_client: Optional[httpx.Client] = None
_client_lock = threading.Lock()

# Cache em memória para evitar re-scraping da mesma música (LRU simples)
_translation_cache: Dict[str, "TranslationResult"] = {}
_translation_cache_lock = threading.Lock()
_MAX_CACHE_SIZE = 60

# Marca, por thread, se alguma requisição falhou de forma transitória (rede, 403, 429, 5xx).
# Resultados vazios causados por falhas transitórias não são cacheados.
_request_state = threading.local()

# Termos que indicam uma versão alternativa da música (penalizados se o título original não os tiver)
VERSION_TERMS = re.compile(
    r'(?<!\w)(?:remix|live|ao vivo|en vivo|ver\.|version|vers[aã]o|acoustic|ac[uú]stico|cover|instrumental|sped up|slowed|nightcore|karaok[eê])(?!\w)',
    re.IGNORECASE
)


def version_penalty(candidate_title: str, original_title: str) -> float:
    """Penaliza candidatos com marcadores de versão (remix, live...) ausentes no título original."""
    orig_terms = {m.lower() for m in VERSION_TERMS.findall(original_title or "")}
    cand_terms = {m.lower() for m in VERSION_TERMS.findall(candidate_title or "")}
    return 1.5 if (cand_terms - orig_terms) else 0.0


@dataclass
class TranslationResult:
    lyrics_dict: Dict[str, str] = field(default_factory=dict)
    ordered_verses: List[Dict[str, Any]] = field(default_factory=list)
    url: Optional[str] = None
    lang_used: Optional[str] = None   # Idioma da tradução efetivamente carregada (None se não houver)
    song_found: bool = False          # A música existe no Letras (mesmo sem tradução)


def _mark_transient_failure():
    _request_state.transient_failure = True


def get_client() -> httpx.Client:
    """Retorna cliente HTTP persistente mantendo cookies e sessao para evitar bloqueios WAF (403)."""
    global _client
    with _client_lock:
        if _client is None or _client.is_closed:
            _client = httpx.Client(
                headers=HEADERS,
                follow_redirects=True,
                timeout=10.0
            )
            try:
                # Aquecimento de cookies (sgroup, countryCode)
                _client.get(BASE_URL, timeout=5.0)
            except Exception:
                pass
        return _client


def fetch_response(url: str, timeout: float = 8.0) -> Optional[httpx.Response]:
    """Executa requisicao GET com renovacao automatica de sessao em caso de 403."""
    client = get_client()
    try:
        res = client.get(url, timeout=timeout)
        if res.status_code == 403:
            logger.info(f"Status 403 ao acessar {url}. Tentando renovar cookies da sessao...")
            with _client_lock:
                try:
                    client.get(BASE_URL, timeout=5.0)
                except Exception:
                    pass
            res = client.get(url, timeout=timeout)
        if res.status_code in (403, 429) or res.status_code >= 500:
            _mark_transient_failure()
        return res
    except Exception as e:
        logger.warning(f"Erro na requisicao para {url}: {e}")
        _mark_transient_failure()
        return None




def remove_accents(input_str: str) -> str:
    """Remove acentos sem decompor caracteres com dakuten/handakuten japoneses."""
    res = []
    for c in input_str:
        if '\u3040' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9fff':
            res.append(c)
        else:
            nfkd = unicodedata.normalize('NFKD', c)
            res.append("".join([ch for ch in nfkd if not unicodedata.combining(ch)]))
    return "".join(res)


def slugify(text: str) -> str:
    """Converte texto em slug para URL: 'Michael Jackson' -> 'michael-jackson'."""
    text = remove_accents(text).lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text


def is_latin(text: str) -> bool:
    """Retorna True se contiver letras do alfabeto latino (A-Z)."""
    return bool(re.search(r'[a-zA-Z]', text))


def is_non_latin(text: str) -> bool:
    """Retorna True se contiver caracteres CJK (japonês, chinês, coreano), cirílico, etc."""
    return bool(re.search(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af\u0400-\u04ff]', text))


def is_japanese(text: str) -> bool:
    """Retorna True se contiver caracteres japoneses (Hiragana, Katakana ou Kanji)."""
    return bool(re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', text))


def clean_song_title(title: str) -> str:
    """
    Remove termos extras comuns como (Official Video), (part. X), (feat. X), Remastered,
    além de desconsiderar blocos entre parênteses/colchetes no final do título
    (ex: transliterações como '(bazovyj minimum)', '(feat. SABI)', '(qualquer coisa)', etc.).
    """
    if not title:
        return ""

    # 1. Remove blocos parentizados ou colchetes contendo termos comuns de metadata
    cleaned = re.sub(
        r'\([^)]*?(?:official|audio|video|clipe?|clip|visualizer|lyric|remaster|vers[aã]o|live|ao vivo|feat|ft\.|part\.|prod\.|legendado|tradu[cç][aã]o|extended)[^)]*?\)',
        '', title, flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r'\[[^\]]*?(?:official|audio|video|clipe?|clip|visualizer|lyric|remaster|vers[aã]o|live|ao vivo|feat|ft\.|part\.|prod\.|legendado|tradu[cç][aã]o|extended)[^\]]*?\]',
        '', cleaned, flags=re.IGNORECASE
    )


    # 2. Remove menções soltas de feat/ft/part no final da string
    cleaned = re.sub(r'\b(?:feat|ft|part|prod)\.?\s+.*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'-\s*(?:remastered|live|official|audio|video).*$', '', cleaned, flags=re.IGNORECASE)

    # 3. Desconsidera iterativamente parênteses/colchetes no final do título
    # Ex: 'Базовый минимум (bazovyj minimum) (feat. SABI)' -> 'Базовый минимум'
    prev = None
    curr = cleaned.strip()
    while prev != curr:
        prev = curr
        curr = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]\s*$', '', curr).strip()

    # 4. Remove pontuação solta residual no final (traços, barras, etc.)
    curr = re.sub(r'[\s\-_/:|]+$', '', curr).strip()
    return curr


def split_multilingual(text: str) -> List[str]:
    """
    Separa títulos/nomes multilíngues (ex: 'ブルーバード - Blue Bird' -> ['Blue Bird', 'ブルーバード']).
    Prioriza versões latinas/romaji e japonês nativo sem termos de part./feat.
    Também divide múltiplos artistas separados por vírgula, &, x, feat, etc.
    """
    if not text:
        return []

    candidates: List[str] = []
    text_clean = clean_song_title(text)

    # 1. Separadores comuns: ' - ', ' / ', '|', '×', ',', '&', ' feat. ', ' ft. ', ' e ', ' and '
    parts = re.split(r'\s*(?:[-/|×,&]|(?:\b(?:feat|ft|part|and|e)\.?\b))\s*', text, flags=re.IGNORECASE)
    latin_parts = [clean_song_title(p.strip()) for p in parts if is_latin(p) and not is_non_latin(p)]
    non_latin_parts = [clean_song_title(p.strip()) for p in parts if is_non_latin(p)]

    # 2. Parênteses: 'Nome (Name)' ou 'Name (Nome)'
    match_paren = re.search(r'^(.*?)\s*[\(\[]([^\)\]]+)[\)\]](.*)$', text)
    if match_paren:
        p1 = clean_song_title((match_paren.group(1) + ' ' + match_paren.group(3)).strip())
        p2 = clean_song_title(match_paren.group(2).strip())
        for p in [p1, p2]:
            if is_latin(p) and not is_non_latin(p) and p not in latin_parts:
                latin_parts.append(p)
            elif is_non_latin(p) and p not in non_latin_parts:
                non_latin_parts.append(p)

    # 3. Transliteração Romaji exclusivamente para nomes nativos em japonês
    romaji_parts = []
    for nlp in non_latin_parts + [text_clean]:
        if is_japanese(nlp):
            hep = to_romaji(nlp)
            if hep and hep not in latin_parts and hep not in romaji_parts:
                romaji_parts.append(hep)

    # Ordem: 1º Latino / Romaji, 2º Nativo Não-Latino, 3º Texto limpo
    for p in latin_parts + romaji_parts + non_latin_parts:
        if p and p not in candidates:
            candidates.append(p)
    if text_clean and text_clean not in candidates:
        candidates.append(text_clean)

    return candidates


def search_letras_fallback(
    query: str,
    expected_titles: Optional[List[str]] = None,
    expected_artists: Optional[List[str]] = None
) -> Optional[str]:
    """Busca direta no mecanismo de busca Solr (JSONP) do Letras.mus.br com validação do resultado."""
    try:
        logger.info(f"Consultando busca do Letras.mus.br para: '{query}'...")
        url = f"https://solr.sscdn.co/letras/m1/?q={urllib.parse.quote(query)}"
        res = fetch_response(url, timeout=6.0)
        if res and res.status_code == 200:
            match = re.search(r'LetrasSug\((.*)\)', res.text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
            else:
                data = res.json()

            docs = data.get("response", {}).get("docs", [])
            # Filtra apenas docs do tipo música (t == '2')
            song_docs = [d for d in docs if d.get("t") == "2" and d.get("dns") and d.get("url")]
            if not song_docs:
                logger.info(f"Nenhuma música encontrada via busca para '{query}'.")
                return None

            # Se informamos títulos esperados, valida que o resultado pertence à mesma faixa
            if expected_titles:
                exp_slugs = [slugify(clean_song_title(t)) for t in expected_titles if t]
                exp_raws = [clean_song_title(t).lower() for t in expected_titles if t]
                matched_docs: List[Tuple[float, int, Dict[str, Any]]] = []

                for doc_idx, doc in enumerate(song_docs):
                    if expected_artists:
                        doc_art = doc.get("art", "").lower()
                        doc_dns = doc.get("dns", "").lower()
                        art_matched = False
                        for ea in expected_artists:
                            ea_clean = clean_song_title(ea).lower()
                            ea_slug = slugify(ea)
                            if (ea_clean and (ea_clean in doc_art or doc_art in ea_clean)) or (ea_slug and (ea_slug in doc_dns or doc_dns in ea_slug)):
                                art_matched = True
                                break
                        if not art_matched:
                            continue

                    doc_title = doc.get("txt", "")
                    doc_url = doc.get("url", "").lower()
                    doc_cands = [doc_title, clean_song_title(doc_title)] + split_multilingual(doc_title)
                    doc_slugs = [slugify(c) for c in doc_cands if c]
                    doc_lowers = [c.lower() for c in doc_cands if c]

                    matched = False
                    for es in exp_slugs:
                        if not es:
                            continue
                        for ds in doc_slugs:
                            if es == ds or es in ds or ds in es:
                                matched = True
                                break
                            if len(es) >= 6 and len(ds) >= 6:
                                if es.replace('ou', 'o') == ds.replace('ou', 'o') or difflib.SequenceMatcher(None, es.replace('ou', 'o'), ds.replace('ou', 'o')).ratio() >= 0.85:
                                    matched = True
                                    break
                        if es in doc_url or doc_url.endswith(f"/{es}") or (len(es) >= 6 and es.replace('ou', 'o') in doc_url.replace('ou', 'o')):
                            matched = True
                        if matched:
                            break

                    if not matched:
                        for er in exp_raws:
                            if not er:
                                continue
                            for dl in doc_lowers:
                                if er == dl or er in dl or dl in er:
                                    matched = True
                                    break
                            if matched:
                                break

                    if matched:
                        penalty = version_penalty(doc_title, " ".join(expected_titles))
                        matched_docs.append((penalty, doc_idx, doc))

                if matched_docs:
                    # Prefere a versão original (sem remix/live...) mantendo a ordem de relevância da busca
                    _, _, doc = min(matched_docs, key=lambda m: (m[0], m[1]))
                    found_path = f"/{doc.get('dns')}/{doc.get('url')}"
                    logger.info(f"Busca encontrou correspondência validada: {found_path} ('{doc.get('txt')}' por '{doc.get('art')}')")
                    return found_path

                logger.info(f"Nenhum resultado da busca correspondeu aos títulos esperados: {expected_titles}")
                return None

            # Se não especificou títulos esperados (busca com artista completo), usa o 1º doc
            doc = song_docs[0]
            found_path = f"/{doc.get('dns')}/{doc.get('url')}"
            logger.info(f"Busca encontrou correspondência direta: {found_path} ('{doc.get('txt')}' por '{doc.get('art')}')")
            return found_path

        logger.info(f"Nenhuma música encontrada via busca para '{query}'.")
    except Exception as e:
        logger.warning(f"Erro na busca do Letras: {e}")
    return None


def find_best_song_link(links: List[Any], title_candidates: List[str], original_title: str) -> Optional[Tuple[str, str]]:
    """
    Escolhe o link da página do artista que melhor corresponde ao título.
    Correspondência exata vence a aproximada, e versões alternativas (remix, live...)
    perdem pontos quando o título original não as menciona.
    Em empate, vale a ordem dos candidatos de título e dos links na página.
    """
    # Pré-processa cada link uma única vez
    entries = []
    for a_tag in links:
        tag_title = (a_tag.get("title") or a_tag.get_text() or "").strip()
        if not tag_title:
            continue
        tag_cands = [tag_title, clean_song_title(tag_title)] + split_multilingual(tag_title)
        entries.append((
            a_tag["href"],
            tag_title,
            [slugify(c) for c in tag_cands if c],
            [c.lower() for c in tag_cands if c],
            version_penalty(tag_title, original_title),
        ))

    best: Optional[Tuple[float, str, str]] = None
    for t_cand in title_candidates:
        cleaned_t = clean_song_title(t_cand)
        title_slug = slugify(cleaned_t)
        if not title_slug:
            continue

        for href, tag_title, tag_slugs, tag_lowers, penalty in entries:
            href_lower = href.lower()
            score = 0.0
            if tag_title.lower() == cleaned_t.lower() or tag_slugs[0] == title_slug:
                score = 3.0
            elif cleaned_t.lower() in tag_lowers or title_slug in tag_slugs:
                score = 2.0
            elif href_lower.rstrip("/").endswith(f"/{title_slug}"):
                score = 2.0
            elif any(len(title_slug) >= 6 and len(ts) >= 6 and title_slug.replace('ou', 'o') == ts.replace('ou', 'o') for ts in tag_slugs):
                score = 1.5
            elif any(len(title_slug) >= 5 and len(ts) >= 5 and difflib.SequenceMatcher(None, title_slug, ts).ratio() >= 0.82
                     for ts in tag_slugs):
                score = 1.2  # Grafia levemente diferente (acento, apóstrofo, letra trocada)
            elif len(title_slug) >= 6 and title_slug.replace('ou', 'o') in href_lower.replace('ou', 'o'):
                score = 1.0

            if score <= 0:
                continue
            score = max(0.1, score - penalty)
            if best is None or score > best[0]:
                best = (score, href, tag_title)
                if score >= 3.0:
                    return href, tag_title

    return (best[1], best[2]) if best else None


def get_song_url(artist: str, song_name: str) -> Optional[str]:
    """
    Localiza a URL da música no Letras.mus.br testando as variações de título
    (priorizando primeiro a versão em inglês/alfabeto latino).
    """
    title_candidates = split_multilingual(song_name)
    # O nome completo do artista vem primeiro (ex: 'Peter, Paul and Mary' antes de 'Peter', 'Paul', 'Mary')
    full_artist = clean_song_title(artist)
    artist_candidates = [full_artist] if full_artist else []
    artist_candidates += [c for c in split_multilingual(artist) if c not in artist_candidates]

    logger.info(f"Candidatos de título: {title_candidates}")
    logger.info(f"Candidatos de artista: {artist_candidates}")

    # 1. Tenta encontrar na página do artista
    checked_slugs = set()
    for a_cand in artist_candidates:
        artist_slug = slugify(a_cand)
        if not artist_slug or artist_slug in checked_slugs:
            continue
        checked_slugs.add(artist_slug)

        artist_url = f"{BASE_URL}/{artist_slug}/"
        logger.info(f"Verificando página do artista: {artist_url}")

        try:
            res = fetch_response(artist_url, timeout=6.0)
            if res and res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                links = soup.find_all("a", href=True)
                best = find_best_song_link(links, title_candidates, song_name)
                if best:
                    href, tag_title = best
                    logger.info(f"Encontrado link por correspondência: {href} ('{tag_title}')")
                    return href
        except Exception as e:
            logger.warning(f"Erro ao acessar {artist_url}: {e}")

    # 2. Se não achou na página do artista, tenta a busca Solr combinada (artista + música)
    for t_cand in title_candidates:
        for a_cand in artist_candidates:
            query = f"{a_cand} {t_cand}".strip()
            path = search_letras_fallback(query, expected_titles=title_candidates)
            if path:
                return path

    # 3. Tentativa com o título validado contra os candidatos de música e artista (evita músicas aleatórias)
    for t_cand in title_candidates:
        path = search_letras_fallback(t_cand, expected_titles=title_candidates, expected_artists=artist_candidates)
        if path:
            return path

    return None


def get_translation_suffix(lang: str = DEFAULT_LANGUAGE) -> str:
    """Retorna o sufixo da página de tradução do Letras.mus.br para o idioma (padrão: PT)."""
    language = LANGUAGES.get(normalize_lang(lang)) or LANGUAGES[DEFAULT_LANGUAGE]
    return language.letras_suffix


def _parse_translation_page(html: str) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Extrai os pares (original -> tradução) e os versos ordenados de uma página de tradução."""
    soup = BeautifulSoup(html, "html.parser")
    lyrics_dict: Dict[str, str] = {}
    ordered_verses: List[Dict[str, Any]] = []

    # Procura versos em <span class="verse">
    verses = soup.find_all("span", class_="verse")
    logger.info(f"Encontradas {len(verses)} tags <span class='verse'>.")

    if verses:
        for verse in verses:
            spans = verse.find_all("span", recursive=False)
            current_origs: List[str] = []
            translation_line = ""

            if len(spans) >= 2:
                translation_line = spans[0].get_text(strip=True)
                orig_container = spans[1]
                sub_spans = orig_container.find_all("span")
                if sub_spans:
                    for s in sub_spans:
                        txt = s.get_text(strip=True)
                        if txt:
                            lyrics_dict[txt] = translation_line
                            current_origs.append(txt)
                else:
                    orig = orig_container.get_text(strip=True)
                    if orig:
                        lyrics_dict[orig] = translation_line
                        current_origs.append(orig)
            else:
                rom = verse.find("span", class_="romanization")
                if rom:
                    sub = rom.find_all("span")
                    rom.extract()
                    translation_line = verse.get_text(strip=True)
                    if sub:
                        for s in sub:
                            txt = s.get_text(strip=True)
                            if txt:
                                lyrics_dict[txt] = translation_line
                                current_origs.append(txt)
                    else:
                        orig = rom.get_text(strip=True)
                        if orig:
                            lyrics_dict[orig] = translation_line
                            current_origs.append(orig)

            if translation_line:
                ordered_verses.append({
                    "index": len(ordered_verses),
                    "translation": translation_line,
                    "originals": current_origs
                })

    # Fallback para páginas com colunas separadas (lyric-translation-left/right ou lyric-original/lyric-translation)
    if not lyrics_dict:
        logger.info("Tentando extração alternativa em colunas de tradução...")
        left_div = soup.find("div", class_="lyric-translation-left")
        lyrics_div = left_div or soup.find("div", class_="lyric-original")
        translation_div = (
            soup.find("div", class_="lyric-translation-right")
            or (soup.find("div", class_="lyric-translation") if not left_div else None)
            or soup.find("div", class_="translation-single")
        )
        if lyrics_div and translation_div:
            # Linhas vazias saem antes do zip, para não desalinhar original e tradução
            orig_paragraphs = [[ln.strip() for ln in p.get_text(separator="\n").split("\n") if ln.strip()]
                               for p in lyrics_div.find_all("p")]
            trans_paragraphs = [[ln.strip() for ln in p.get_text(separator="\n").split("\n") if ln.strip()]
                                for p in translation_div.find_all("p")]
            for orig_p, trans_p in zip(orig_paragraphs, trans_paragraphs):
                for orig_line, trans_line in zip(orig_p, trans_p):
                    o_clean = orig_line.strip()
                    t_clean = trans_line.strip()
                    if o_clean and t_clean:
                        lyrics_dict[o_clean] = t_clean
                        ordered_verses.append({
                            "index": len(ordered_verses),
                            "translation": t_clean,
                            "originals": [o_clean]
                        })

    return lyrics_dict, ordered_verses


def clear_translation_cache():
    """Esquece as traduções em memória (usado em "Recarregar letra")."""
    with _translation_cache_lock:
        _translation_cache.clear()


def _cache_put(key: str, result: TranslationResult):
    with _translation_cache_lock:
        if len(_translation_cache) >= _MAX_CACHE_SIZE:
            _translation_cache.pop(next(iter(_translation_cache)))
        _translation_cache[key] = result


def letras_path_from_url(text: str) -> Optional[str]:
    """
    Extrai o caminho da música de uma URL do Letras.mus.br colada pelo usuário:
    'https://www.letras.mus.br/ado/odo/traducao.html' -> '/ado/odo/'. Retorna None se não for uma URL válida.
    """
    text = (text or "").strip()
    if "letras.mus.br" in text:
        text = text.split("letras.mus.br", 1)[1]
    match = re.match(r'(/[^/\s?#]+/[^/\s?#]+)', text)
    return match.group(1) + "/" if match else None


def fetch_translation(
    artist: str,
    song_name: str,
    lang: str = "pt",
    allow_pt_fallback: bool = True,
    song_path: Optional[str] = None,
) -> TranslationResult:
    """
    Obtém a tradução verso a verso da música no Letras.mus.br no idioma escolhido.
    Sufixos suportados:
      - pt (ou pt-br): traducao.html
      - fr: traduction-francaise.html
      - en: english.html
      - es: traduccion.html
    Se o idioma pedido não existir e allow_pt_fallback=True, usa a tradução em PT
    (o idioma efetivamente carregado fica em result.lang_used).
    Resultados definitivos (inclusive "não encontrado") são cacheados; falhas transitórias
    de rede/bloqueio não, para que a próxima tentativa busque de novo.
    `song_path` (ex: '/ado/odo/') pula a busca e usa diretamente essa página do Letras.
    """
    lang = (lang or "pt").lower().strip()
    cache_key = f"{artist.lower().strip()}|||{song_name.lower().strip()}|||{lang}|||{int(allow_pt_fallback)}|||{song_path or ''}"
    with _translation_cache_lock:
        if cache_key in _translation_cache:
            logger.info(f"[CACHE] Hit para '{song_name}' ({lang.upper()}) — pulando scraping.")
            return _translation_cache[cache_key]

    _request_state.transient_failure = False
    result = TranslationResult()

    song_path = song_path or get_song_url(artist, song_name)
    if not song_path:
        logger.info(f"Música '{song_name}' de '{artist}' NÃO encontrada no Letras.mus.br.")
        if not _request_state.transient_failure:
            _cache_put(cache_key, result)
        return result

    result.song_found = True
    if not song_path.endswith("/"):
        song_path += "/"

    attempts = [(lang, get_translation_suffix(lang))]
    if allow_pt_fallback and attempts[0][1] != "traducao.html":
        attempts.append(("pt", "traducao.html"))

    for attempt_lang, suffix in attempts:
        url_translation = f"{BASE_URL}{song_path}{suffix}"
        result.url = url_translation
        logger.info(f"Acessando página de tradução ({attempt_lang}): {url_translation}")
        res = fetch_response(url_translation, timeout=8.0)
        status_code = res.status_code if res else 0
        logger.info(f"Status da página de tradução: {status_code}")
        if status_code != 200:
            continue

        try:
            lyrics_dict, ordered_verses = _parse_translation_page(res.text)
        except Exception as e:
            logger.warning(f"Erro ao extrair tradução de {url_translation}: {e}")
            _mark_transient_failure()
            continue

        if ordered_verses or lyrics_dict:
            result.lyrics_dict = lyrics_dict
            result.ordered_verses = ordered_verses
            result.lang_used = attempt_lang
            logger.info(f"Sucesso! Total de {len(lyrics_dict)} versos carregados ({len(ordered_verses)} versos ordenados) em {attempt_lang.upper()}.")
            break

    if result.lang_used and result.lang_used != lang:
        logger.info(f"Idioma '{lang}' não disponível; usando tradução em '{result.lang_used}'.")

    if result.lang_used or not _request_state.transient_failure:
        _cache_put(cache_key, result)
    return result


def get_translation(artist: str, song_name: str, lang: str = "pt") -> Tuple[Dict[str, str], List[Dict[str, Any]], Optional[str]]:
    """
    Compatibilidade: retorna (lyrics_dict, ordered_verses, translation_url).
      - lyrics_dict: { "linha original": "linha traduzida" }
      - ordered_verses: [{"index": 0, "translation": "...", "originals": [...]}, ...]
    """
    result = fetch_translation(artist, song_name, lang)
    return result.lyrics_dict, result.ordered_verses, result.url
