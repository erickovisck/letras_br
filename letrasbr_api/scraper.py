import re
import json
import unicodedata
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Tuple, Optional, Any

BASE_URL = "https://www.letras.mus.br"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def log(msg: str):
    try:
        print(f"[SCRAPER] {msg}")
    except Exception:
        safe_msg = str(msg).encode("ascii", "replace").decode("ascii")
        print(f"[SCRAPER] {safe_msg}")


try:
    import pykakasi
    _kks = pykakasi.kakasi()
except Exception:
    _kks = None


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
    # Usar [^)]* e [^\]]* garante que parênteses independentes não sejam agrupados indevidamente
    cleaned = re.sub(
        r'\([^)]*?(?:official|audio|video|remaster|vers[aã]o|live|ao vivo|feat|ft\.|part\.|prod\.)[^)]*?\)',
        '', title, flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r'\[[^\]]*?(?:official|audio|video|remaster|vers[aã]o|live|ao vivo|feat|ft\.|part\.|prod\.)[^\]]*?\]',
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

    # 1. Separadores comuns: ' - ', ' / ', '|', '×', ',', '&', ' feat. ', ' ft. '
    parts = re.split(r'\s*(?:[-/|×,&]|(?:\b(?:feat|ft|part)\.?\b))\s*', text)
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
    if _kks:
        for nlp in non_latin_parts + [text_clean]:
            if is_japanese(nlp):
                try:
                    conv = _kks.convert(nlp)
                    hep = " ".join([item["hepburn"] for item in conv]).strip()
                    if hep and hep not in latin_parts and hep not in romaji_parts:
                        romaji_parts.append(hep)
                except Exception:
                    pass

    # Ordem: 1º Latino / Romaji, 2º Nativo Não-Latino, 3º Texto limpo
    for p in latin_parts + romaji_parts + non_latin_parts:
        if p and p not in candidates:
            candidates.append(p)
    if text_clean and text_clean not in candidates:
        candidates.append(text_clean)

    return candidates


def search_letras_fallback(query: str, expected_titles: Optional[List[str]] = None) -> Optional[str]:
    """Busca direta no mecanismo de busca Solr (JSONP) do Letras.mus.br com validação do resultado."""
    try:
        log(f"Consultando busca do Letras.mus.br para: '{query}'...")
        url = f"https://solr.sscdn.co/letras/m1/?q={requests.utils.quote(query)}"
        res = requests.get(url, headers=HEADERS, timeout=6)
        if res.status_code == 200:
            match = re.search(r'LetrasSug\((.*)\)', res.text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
            else:
                data = res.json()

            docs = data.get("response", {}).get("docs", [])
            # Filtra apenas docs do tipo música (t == '2')
            song_docs = [d for d in docs if d.get("t") == "2" and d.get("dns") and d.get("url")]
            if not song_docs:
                log(f"Nenhuma música encontrada via busca para '{query}'.")
                return None

            # Se informamos títulos esperados, valida que o resultado pertence à mesma faixa
            if expected_titles:
                exp_slugs = [slugify(clean_song_title(t)) for t in expected_titles if t]
                exp_raws = [clean_song_title(t).lower() for t in expected_titles if t]

                for doc in song_docs:
                    doc_title = doc.get("txt", "")
                    cleaned_doc_title = clean_song_title(doc_title)
                    doc_slug = slugify(cleaned_doc_title)
                    doc_url = doc.get("url", "").lower()
                    doc_lower = cleaned_doc_title.lower()

                    for es in exp_slugs:
                        if es and (es == doc_slug or es in doc_url or doc_slug in es):
                            found_path = f"/{doc.get('dns')}/{doc.get('url')}"
                            log(f"Busca encontrou correspondência validada: {found_path} ('{doc_title}' por '{doc.get('art')}')")
                            return found_path

                    for er in exp_raws:
                        if er and (er in doc_lower or doc_lower in er):
                            found_path = f"/{doc.get('dns')}/{doc.get('url')}"
                            log(f"Busca encontrou correspondência validada por texto: {found_path} ('{doc_title}' por '{doc.get('art')}')")
                            return found_path

                log(f"Nenhum resultado da busca correspondeu aos títulos esperados: {expected_titles}")
                return None

            # Se não especificou títulos esperados (busca com artista completo), usa o 1º doc
            doc = song_docs[0]
            found_path = f"/{doc.get('dns')}/{doc.get('url')}"
            log(f"Busca encontrou correspondência direta: {found_path} ('{doc.get('txt')}' por '{doc.get('art')}')")
            return found_path

        log(f"Nenhuma música encontrada via busca para '{query}'.")
    except Exception as e:
        log(f"Erro na busca do Letras: {e}")
    return None


def get_song_url(artist: str, song_name: str) -> Optional[str]:
    """
    Localiza a URL da música no Letras.mus.br testando as variações de título
    (priorizando primeiro a versão em inglês/alfabeto latino).
    """
    title_candidates = split_multilingual(song_name)
    artist_candidates = split_multilingual(artist)

    log(f"Candidatos de título: {title_candidates}")
    log(f"Candidatos de artista: {artist_candidates}")

    # 1. Tenta encontrar na página do artista
    for a_cand in artist_candidates:
        artist_slug = slugify(a_cand)
        if not artist_slug:
            continue

        artist_url = f"{BASE_URL}/{artist_slug}/"
        log(f"Verificando página do artista: {artist_url}")

        try:
            res = requests.get(artist_url, headers=HEADERS, timeout=6)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                links = soup.find_all("a", href=True)

                for t_cand in title_candidates:
                    cleaned_t = clean_song_title(t_cand)
                    title_slug = slugify(cleaned_t)

                    # Busca por title exato ou título limpo nos links
                    for a_tag in links:
                        tag_title = a_tag.get("title") or a_tag.get_text()
                        if not tag_title:
                            continue
                        cleaned_tag = clean_song_title(tag_title)
                        if cleaned_tag.lower() == cleaned_t.lower() or slugify(cleaned_tag) == title_slug:
                            log(f"Encontrado link por título limpo: {a_tag['href']} ('{tag_title}')")
                            return a_tag["href"]
                        if a_tag["href"].rstrip("/").endswith(f"/{title_slug}"):
                            log(f"Encontrado link por sufixo de slug: {a_tag['href']}")
                            return a_tag["href"]
        except Exception as e:
            log(f"Erro ao acessar {artist_url}: {e}")

    # 2. Se não achou na página do artista, tenta a busca Solr combinada (artista + música)
    for t_cand in title_candidates:
        for a_cand in artist_candidates:
            query = f"{a_cand} {t_cand}".strip()
            path = search_letras_fallback(query, expected_titles=title_candidates)
            if path:
                return path

    # 3. Tentativa com o título validado contra os candidatos de música (evita músicas aleatórias)
    for t_cand in title_candidates:
        path = search_letras_fallback(t_cand, expected_titles=title_candidates)
        if path:
            return path

    return None


# Mapeamento de idiomas suportados pelo Letras.mus.br e seus sufixos de URL
LANGUAGE_SUFFIXES = {
    "pt": "traducao.html",
    "pt-br": "traducao.html",
    "fr": "traduction-francaise.html",
    "en": "english.html",
    "es": "traduccion.html"
}


def get_translation_suffix(lang: str = "pt") -> str:
    """Retorna o sufixo da URL para o idioma especificado ('pt', 'fr', 'en', 'es')."""
    return LANGUAGE_SUFFIXES.get((lang or "").lower().strip(), "traducao.html")


def get_translation(artist: str, song_name: str, lang: str = "pt") -> Tuple[Dict[str, str], List[Dict[str, Any]], Optional[str]]:
    """
    Obtém a tradução verso a verso da música no Letras.mus.br no idioma escolhido.
    Sufixos suportados:
      - pt (ou pt-br): traducao.html
      - fr: traduction-francaise.html
      - en: english.html
      - es: traduccion.html
    Retorna:
      - lyrics_dict: { "linha original": "linha traduzida" }
      - ordered_verses: [{"index": 0, "translation": "...", "originals": [...]}, ...]
      - translation_url: URL da página de tradução encontrada
    """
    song_path = get_song_url(artist, song_name)
    if not song_path:
        log(f"Música '{song_name}' de '{artist}' NÃO encontrada no Letras.mus.br.")
        return {}, [], None

    if not song_path.endswith("/"):
        song_path += "/"

    suffix = get_translation_suffix(lang)
    url_translation = f"{BASE_URL}{song_path}{suffix}"
    log(f"Acessando página de tradução ({lang}): {url_translation}")

    lyrics_dict: Dict[str, str] = {}
    ordered_verses: List[Dict[str, Any]] = []

    try:
        res = requests.get(url_translation, headers=HEADERS, timeout=6)
        log(f"Status da página de tradução: {res.status_code}")
        # Se o idioma alternativo (ex: francês ou espanhol) não existir para esta música, tenta fallback para PT
        if res.status_code != 200 and suffix != "traducao.html":
            log(f"Idioma '{lang}' não disponível (HTTP {res.status_code}). Tentando fallback para PT (traducao.html)...")
            url_translation = f"{BASE_URL}{song_path}traducao.html"
            res = requests.get(url_translation, headers=HEADERS, timeout=6)
            log(f"Status do fallback PT: {res.status_code}")

        if res.status_code != 200:
            log(f"Página de tradução retornou {res.status_code}.")
            return {}, [], url_translation

        soup = BeautifulSoup(res.text, "html.parser")

        # Procura versos em <span class="verse">
        verses = soup.find_all("span", class_="verse")
        log(f"Encontradas {len(verses)} tags <span class='verse'>.")

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

        # Fallback alternativo para páginas antigas com divs separados
        if not lyrics_dict:
            log("Tentando extração alternativa em lyric-original e lyric-translation...")
            lyrics_div = soup.find("div", class_="lyric-original")
            translation_div = soup.find("div", class_="lyric-translation") or soup.find("div", class_="translation-single")
            if lyrics_div and translation_div:
                orig_paragraphs = [p.get_text(separator="\n").split("\n") for p in lyrics_div.find_all("p")]
                trans_paragraphs = [p.get_text(separator="\n").split("\n") for p in translation_div.find_all("p")]
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

        log(f"Sucesso! Total de {len(lyrics_dict)} versos carregados ({len(ordered_verses)} versos ordenados).")

    except Exception as e:
        log(f"Erro ao extrair tradução de {url_translation}: {e}")

    return lyrics_dict, ordered_verses, url_translation
