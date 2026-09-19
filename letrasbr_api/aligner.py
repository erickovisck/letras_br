import re
import difflib
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

try:
    import pykakasi
    _kks = pykakasi.kakasi()
except Exception:
    _kks = None


@dataclass
class AlignedLine:
    start_time: int
    end_time: int
    original: str
    translation: str
    is_instrumental: bool


def is_instrumental(text: str) -> bool:
    """Verifica se a linha é apenas instrumental / notas musicais (♪, ♫, etc.) ou vazia."""
    if not text:
        return True
    cleaned = re.sub(r"[\s\(\)\[\]\u2669-\u266f\u266a♫♪♩♬~〜\-–—.]+", "", text)
    return len(cleaned) == 0


def normalize(text: str) -> str:
    """Normaliza o texto para comparação."""
    if not text:
        return ""
    text = re.sub(r"[\u2669-\u266f\u266a♫♪♩♬]", "", text).lower()
    text = re.sub(r"[^\w\s\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]", "", text)
    return re.sub(r"[\s\u3000]+", " ", text).strip()


def get_variants(text: str) -> List[str]:
    """Gera variações de leitura (original, furigana expandido, hiragana, romaji)."""
    vars_list = [text]
    no_paren = re.sub(r"\(.*?\)|\[.*?\]|（.*?）", "", text).strip()
    if no_paren and no_paren not in vars_list:
        vars_list.append(no_paren)

    furigana_exp = re.sub(r"[\u4e00-\u9fff]+\(([\u3040-\u30ff]+)\)", r"\1", text).strip()
    if furigana_exp and furigana_exp not in vars_list:
        vars_list.append(furigana_exp)

    # Conversão nativa Katakana -> Hiragana (sem dependências)
    base_for_kana = furigana_exp or text
    kata_to_hira = "".join(chr(ord(c) - 0x60) if 0x30A1 <= ord(c) <= 0x30F6 else c for c in base_for_kana)
    if kata_to_hira and kata_to_hira not in vars_list:
        vars_list.append(kata_to_hira)

    if _kks:
        try:
            conv = _kks.convert(furigana_exp or text)
            hira = "".join([item["hira"] for item in conv])
            if hira and hira not in vars_list:
                vars_list.append(hira)
            romaji = " ".join([item["hepburn"] for item in conv])
            if romaji and romaji not in vars_list:
                vars_list.append(romaji)
        except Exception:
            pass

    return [normalize(v) for v in vars_list if normalize(v)]


# Mapeamento de leituras fonéticas/irregulares comuns em letras musicais (ateji/furigana)
COMMON_LYRIC_READINGS = {
    "飛翔いたら": ["はばたいたら", "habataitara"],
    "飛翔いて": ["はばたいて", "habataite"],
    "共鳴けて": ["ひびかせて", "hibikasete"],
    "今日は": ["きょうは", "kyou wa", "kyouwa"],
}


def expand_lyric_variants(text: str) -> List[str]:
    """Expande variações textuais incluindo sinônimos fonéticos conhecidos."""
    variants = get_variants(text)
    for k, syns in COMMON_LYRIC_READINGS.items():
        if k in text:
            for s in syns:
                variants.extend(get_variants(text.replace(k, s)))
    return list(dict.fromkeys(variants))


def score_line_match(y_text: str, l_origs: List[str]) -> float:
    """Calcula pontuação de similaridade entre a linha do YTM e os originais do Letras."""
    y_vars = expand_lyric_variants(y_text)
    parts = [p.strip() for p in re.split(r"[\s\u3000]+", y_text) if p.strip()]

    best = 0.0
    for y_v in y_vars:
        for l_orig in l_origs:
            for l_v in expand_lyric_variants(l_orig):
                if y_v == l_v:
                    return 1.0
                if len(y_v) >= 4 and len(l_v) >= 4:
                    if y_v in l_v or l_v in y_v:
                        best = max(best, 0.90)
                ratio = difflib.SequenceMatcher(None, y_v, l_v).ratio()
                if ratio >= 0.50:
                    best = max(best, ratio)

    # Checa também se alguma parte separada por espaço bate
    if len(parts) > 1:
        for p in parts:
            for p_v in expand_lyric_variants(p):
                for l_orig in l_origs:
                    for l_v in expand_lyric_variants(l_orig):
                        if p_v == l_v:
                            best = max(best, 0.88)
                        elif len(p_v) >= 4 and len(l_v) >= 4 and (p_v in l_v or l_v in p_v):
                            best = max(best, 0.80)

    return best

def _smart_assign_gap(
    mid_y_indices: List[int],
    mid_l_indices: List[int],
    timed_lyrics: List[Any],
    vocal_indices: List[int],
    ordered_verses: List[Dict[str, Any]],
    assigned_L: Dict[int, List[str]]
):
    """
    Distribui de forma inteligente e segura os versos do Letras (mid_l_indices)
    entre as linhas vocais do YTM (mid_y_indices) dentro de uma lacuna.
    - Se num_y > num_l (mais linhas no YTM, ex: ad-libs como 'Oh my God'),
      combina as linhas usando DP de similaridade, deixando os ad-libs com score ~0
      sem tradução para não 'roubar' a tradução de versos legítimos vizinhos.
    - Se não houver match claro ou se num_l >= num_y, mantém a distribuição
      proporcional conservadora para nunca quebrar músicas com transliterações diferentes.
    """
    num_y = len(mid_y_indices)
    num_l = len(mid_l_indices)
    if num_l == 0 or num_y == 0:
        return

    # Pareamento direto 1:1 se as quantidades forem idênticas
    if num_y == num_l:
        for k in range(num_y):
            assigned_L[mid_y_indices[k]].append(ordered_verses[mid_l_indices[k]]["translation"])
        return

    # Constrói matriz de similaridade entre versos do Letras e linhas do YTM na lacuna
    matrix = []
    has_any_good_match = False
    for lj in mid_l_indices:
        row = []
        l_origs = ordered_verses[lj].get("originals", [])
        for yi in mid_y_indices:
            y_text = timed_lyrics[vocal_indices[yi]].text
            sc = score_line_match(y_text, l_origs)
            if sc >= 0.30:
                has_any_good_match = True
            row.append(sc)
        matrix.append(row)

    # Mais versos no Letras do que linhas no YTM (num_l > num_y)
    # Linhas longas do YTM podem agrupar múltiplos versos curtos do Letras
    if num_l > num_y:
        if has_any_good_match:
            memo = {}

            def solve_more_l(l_idx, y_curr):
                if l_idx == num_l:
                    if y_curr == num_y - 1:
                        return 0.0, []
                    return -1e9, []
                if (num_l - l_idx) < (num_y - 1 - y_curr):
                    return -1e9, []
                key = (l_idx, y_curr)
                if key in memo:
                    return memo[key]

                sc = matrix[l_idx][y_curr]
                bonus = sc if sc > 0 else 0.001

                # Opção 1: continuar na mesma linha YTM
                v1, p1 = solve_more_l(l_idx + 1, y_curr)
                val1 = v1 + bonus

                # Opção 2: avançar para a próxima linha YTM
                val2 = -1e9
                p2 = []
                if y_curr + 1 < num_y:
                    v2, p2 = solve_more_l(l_idx + 1, y_curr + 1)
                    val2 = v2 + bonus

                if val2 >= val1:
                    best_val = val2
                    best_path = [(l_idx, y_curr)] + p2
                else:
                    best_val = val1
                    best_path = [(l_idx, y_curr)] + p1

                memo[key] = (best_val, best_path)
                return memo[key]

            val, best_path = solve_more_l(0, 0)
            if best_path and val > -1e8:
                for l_idx, y_idx in best_path:
                    assigned_L[mid_y_indices[y_idx]].append(ordered_verses[mid_l_indices[l_idx]]["translation"])
                return

        # Distribuição balanceada central caso não haja match textual seguro
        for k, lj in enumerate(mid_l_indices):
            target_y = mid_y_indices[min(int((k + 0.5) * num_y / num_l), num_y - 1)]
            assigned_L[target_y].append(ordered_verses[lj]["translation"])
        return

    # Mais linhas no YTM do que versos no Letras (num_y > num_l):
    # Cenário de falas extras, exclamações e ad-libs (ex: 'Oh my God')
    # Se nenhum verso tiver score >= 0.30, faz distribuição balanceada conservadora
    if not has_any_good_match:
        for k, lj in enumerate(mid_l_indices):
            target_y = mid_y_indices[min(int((k + 0.5) * num_y / num_l), num_y - 1)]
            assigned_L[target_y].append(ordered_verses[lj]["translation"])
        return

    # Com matches inteligentes, alinha monotonicamente maximizando a pontuação
    memo = {}

    def solve(l_idx, y_start):
        if l_idx == num_l:
            return 0.0, []
        if y_start >= num_y:
            return -1e9, []
        key = (l_idx, y_start)
        if key in memo:
            return memo[key]

        # Opção 1: pular y_start (y_start fica livre e sem tradução)
        best_val, best_path = solve(l_idx, y_start + 1)

        # Opção 2: casar verso l_idx com linha y_start
        sc = matrix[l_idx][y_start]
        bonus = sc if sc > 0 else 0.001
        val_match, path_match = solve(l_idx + 1, y_start + 1)
        if val_match + bonus > best_val:
            best_val = val_match + bonus
            best_path = [(l_idx, y_start)] + path_match

        memo[key] = (best_val, best_path)
        return memo[key]

    _, best_path = solve(0, 0)
    for l_idx, y_idx in best_path:
        assigned_L[mid_y_indices[y_idx]].append(ordered_verses[mid_l_indices[l_idx]]["translation"])


def align_lyrics(
    timed_lyrics: List[Any],
    ordered_verses: List[Dict[str, Any]],
    title: str = "",
    artist: str = "",
    lang: str = ""
) -> List[AlignedLine]:
    """
    Realiza o pré-alinhamento global de todos os versos da música no momento da identificação.
    1. Trata trechos instrumentais (♪).
    2. Identifica âncoras cronológicas através de programação dinâmica monotônica.
    3. Repassa todos os versos e preenche lacunas com inteligência (sem duplicar ou sobrescrever
       versos que já possuem tradução completa).
    4. Registra automaticamente em logs/sem_traducao.log caso haja trechos sem tradução.
    """
    if not timed_lyrics:
        return []

    # 1. Cria lista base
    result: List[Optional[AlignedLine]] = [None] * len(timed_lyrics)

    for i, line in enumerate(timed_lyrics):
        if is_instrumental(line.text):
            result[i] = AlignedLine(
                start_time=line.start_time,
                end_time=line.end_time,
                original="♪",
                translation="(♪)",
                is_instrumental=True
            )

    # Se não temos versos traduzidos do Letras
    if not ordered_verses:
        for i, line in enumerate(timed_lyrics):
            if result[i] is None:
                result[i] = AlignedLine(
                    start_time=line.start_time,
                    end_time=line.end_time,
                    original=line.text,
                    translation="(tradução indisponível)",
                    is_instrumental=False
                )
        final_list = [r for r in result if r is not None]
        if title:
            try:
                from translation_logger import log_untranslated_lyrics
                log_untranslated_lyrics(title, artist, lang, final_list)
            except Exception:
                pass
        return final_list

    # Linhas vocais do YTM
    vocal_indices = [i for i, line in enumerate(timed_lyrics) if result[i] is None]
    if not vocal_indices:
        return [r for r in result if r is not None]

    num_vocal = len(vocal_indices)
    num_letras = len(ordered_verses)

    # 2. Busca candidatos a âncoras (score >= 0.60)
    candidates: List[Tuple[int, int, float]] = []
    for v_idx, y_i in enumerate(vocal_indices):
        y_text = timed_lyrics[y_i].text
        for l_j, l_v in enumerate(ordered_verses):
            sc = score_line_match(y_text, l_v.get("originals", []))
            if sc >= 0.60:
                candidates.append((v_idx, l_j, sc))

    # 3. DP Monotônica para encontrar a melhor sequência de âncoras
    # Permite i_prev <= i_curr (uma linha longa do YTM pode ancorar em múltiplos versos curtos do Letras)
    # Dá um leve bônus (+0.05) para avançar a linha do YTM quando os versos avançam
    candidates.sort(key=lambda x: (x[0], x[1]))
    dp = [c[2] for c in candidates]
    prev = [-1 for _ in candidates]

    for idx in range(len(candidates)):
        i_curr, j_curr, sc_curr = candidates[idx]
        for p_idx in range(idx):
            i_prev, j_prev, _ = candidates[p_idx]
            if i_prev <= i_curr and j_prev < j_curr:
                advance_bonus = 0.05 if i_curr > i_prev else 0.0
                val = dp[p_idx] + sc_curr + advance_bonus
                if val > dp[idx]:
                    dp[idx] = val
                    prev[idx] = p_idx

    best_end = max(range(len(candidates)), key=lambda x: dp[x]) if candidates else -1
    anchors: List[Tuple[int, int]] = []
    curr = best_end
    while curr != -1:
        anchors.append((candidates[curr][0], candidates[curr][1]))
        curr = prev[curr]
    anchors.reverse()

    # 4. REPASSE E DISTRIBUIÇÃO DAS LACUNAS (ALINHAMENTO INTELIGENTE)
    assigned_L: Dict[int, List[str]] = {v_i: [] for v_i in range(num_vocal)}

    if not anchors:
        # Se nenhuma âncora textual foi encontrada, usa alinhamento inteligente global
        _smart_assign_gap(
            list(range(num_vocal)),
            list(range(num_letras)),
            timed_lyrics,
            vocal_indices,
            ordered_verses,
            assigned_L
        )
    else:
        # 4.1 Lacuna antes da primeira âncora
        first_y, first_l = anchors[0]
        if first_y > 0 and first_l > 0:
            _smart_assign_gap(
                list(range(0, first_y)),
                list(range(0, first_l)),
                timed_lyrics,
                vocal_indices,
                ordered_verses,
                assigned_L
            )

        # 4.2 Entre âncoras consecutivas
        for a_idx in range(len(anchors)):
            curr_y, curr_l = anchors[a_idx]
            assigned_L[curr_y].append(ordered_verses[curr_l]["translation"])

            if a_idx + 1 < len(anchors):
                next_y, next_l = anchors[a_idx + 1]
                mid_l = list(range(curr_l + 1, next_l))
                mid_y = list(range(curr_y + 1, next_y))

                if mid_l:
                    if mid_y:
                        _smart_assign_gap(
                            mid_y,
                            mid_l,
                            timed_lyrics,
                            vocal_indices,
                            ordered_verses,
                            assigned_L
                        )
                    else:
                        # Mesma linha ou linhas YTM adjacentes: os versos pertencem à linha atual
                        for lj in mid_l:
                            assigned_L[curr_y].append(ordered_verses[lj]["translation"])

        # 4.3 Lacuna após a última âncora
        last_y, last_l = anchors[-1]
        if last_y + 1 < num_vocal and last_l + 1 < num_letras:
            _smart_assign_gap(
                list(range(last_y + 1, num_vocal)),
                list(range(last_l + 1, num_letras)),
                timed_lyrics,
                vocal_indices,
                ordered_verses,
                assigned_L
            )
        elif last_l + 1 < num_letras:
            for lj in range(last_l + 1, num_letras):
                assigned_L[last_y].append(ordered_verses[lj]["translation"])

    # 4.4 Fallback inteligente para versos que ficaram sem tradução (ex: refrões repetidos)
    for v_idx, y_i in enumerate(vocal_indices):
        if not assigned_L[v_idx]:
            best_l = None
            best_sc = 0.0
            for l_v in ordered_verses:
                sc = score_line_match(timed_lyrics[y_i].text, l_v.get("originals", []))
                if sc > best_sc and sc >= 0.60:
                    best_sc = sc
                    best_l = l_v["translation"]
            if best_l:
                assigned_L[v_idx].append(best_l)

    # 5. Monta a lista final alinhada
    for v_idx, y_i in enumerate(vocal_indices):
        line = timed_lyrics[y_i]
        l_list = assigned_L.get(v_idx, [])
        # Remove duplicatas consecutivas na mesma linha preservando ordem
        dedup_l: List[str] = []
        for item in l_list:
            if not dedup_l or dedup_l[-1] != item:
                dedup_l.append(item)

        trans_str = " / ".join(dedup_l) if dedup_l else "(sem tradução para este verso)"

        result[y_i] = AlignedLine(
            start_time=line.start_time,
            end_time=line.end_time,
            original=line.text,
            translation=trans_str,
            is_instrumental=False
        )

    final_list = [r for r in result if r is not None]
    if title:
        try:
            from translation_logger import log_untranslated_lyrics
            log_untranslated_lyrics(title, artist, lang, final_list)
        except Exception:
            pass

    return final_list


def find_active_aligned_line(aligned_lines: List[AlignedLine], current_time_ms: int) -> Optional[AlignedLine]:
    """Busca em tempo real O(N) simples ou direta pela linha correspondente ao timestamp atual."""
    if not aligned_lines:
        return None

    active = None
    for line in aligned_lines:
        if line.start_time <= current_time_ms <= line.end_time:
            return line
        if line.start_time <= current_time_ms:
            active = line

    return active
