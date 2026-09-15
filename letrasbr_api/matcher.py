import re
import unicodedata
import difflib
from typing import Dict, List, Tuple, Optional, Any, Set

try:
    import pykakasi
    _kks = pykakasi.kakasi()
except Exception:
    _kks = None


def is_instrumental(text: str) -> bool:
    """Verifica se a linha é apenas instrumental / notas musicais (♪, ♫, etc.) ou vazia."""
    if not text:
        return True
    cleaned = re.sub(r"[\s\(\)\[\]\u2669-\u266f\u266a♫♪♩♬~〜\-–—.]+", "", text)
    return len(cleaned) == 0


def normalize_lyric_line(text: str) -> str:
    """Normaliza o texto da linha removendo pontuação, notas musicais e espaços extras."""
    if not text:
        return ""
    # Remove símbolos musicais
    text = re.sub(r"[\u2669-\u266f\u266a♫♪♩♬]", "", text)
    # Minúsculas
    text = text.lower()
    # Remove pontuações mantendo letras, números e caracteres alfabéticos/CJK
    text = re.sub(r"[^\w\s\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]", "", text)
    # Remove múltiplos espaços
    text = re.sub(r"[\s\u3000]+", " ", text).strip()
    return text


def strip_furigana(text: str) -> str:
    """Remove conteúdo entre parênteses: 飛翔(はばた)いたら -> 飛翔いたら."""
    return re.sub(r"\(.*?\)|\[.*?\]|（.*?）", "", text).strip()


def extract_furigana_reading(text: str) -> str:
    """Substitui kanji seguido de leitura em parênteses pela leitura: 飛翔(はばた)いたら -> はばたいたら."""
    return re.sub(r"[\u4e00-\u9fff]+\(([\u3040-\u30ff]+)\)", r"\1", text)


def get_text_variants(text: str) -> List[str]:
    """Gera variações de leitura (original, furigana expandido, hiragana, romaji)."""
    variants = [text]

    furigana_expanded = extract_furigana_reading(text)
    if furigana_expanded not in variants:
        variants.append(furigana_expanded)

    no_paren = strip_furigana(text)
    if no_paren not in variants:
        variants.append(no_paren)

    if _kks:
        try:
            conv = _kks.convert(furigana_expanded)
            hira = "".join([item["hira"] for item in conv])
            if hira and hira not in variants:
                variants.append(hira)
            romaji = " ".join([item["hepburn"] for item in conv])
            if romaji and romaji not in variants:
                variants.append(romaji)
        except Exception:
            pass

    return variants


class LyricsMatcher:
    def __init__(self, raw_input: Any, raw_translation_dict: Optional[Dict[str, str]] = None):
        """
        Pode receber:
        - ordered_verses: List[Dict[str, Any]] (com index, translation e originals)
        - raw_translation_dict: Dict[str, str]
        """
        self.ordered_translations: List[str] = []
        # Mapeia texto_normalizado -> (index, traducao)
        self.normalized_map: Dict[str, Tuple[int, str]] = {}
        self.called_indices: Set[int] = set()
        self.last_called_index: int = -1

        if isinstance(raw_input, list) and raw_input and isinstance(raw_input[0], dict):
            # Formato com sequência cronológica ordered_verses
            for item in raw_input:
                idx = item.get("index", len(self.ordered_translations))
                trans = item.get("translation", "")
                self.ordered_translations.append(trans)
                origs = item.get("originals", [])
                for orig in origs:
                    for var in get_text_variants(orig):
                        norm = normalize_lyric_line(var)
                        if norm:
                            self.normalized_map[norm] = (idx, trans)
        else:
            # Fallback para dicionário bruto
            d = raw_input if isinstance(raw_input, dict) else (raw_translation_dict or {})
            for idx, (orig, trans) in enumerate(d.items()):
                self.ordered_translations.append(trans)
                for var in get_text_variants(orig):
                    norm = normalize_lyric_line(var)
                    if norm:
                        self.normalized_map[norm] = (idx, trans)

        self.normalized_keys = list(self.normalized_map.keys())

    def reset_called(self):
        """Reseta o histórico de versos chamados quando a música é reiniciada ou volta no tempo."""
        self.called_indices.clear()
        self.last_called_index = -1

    def _match_exact_single(self, text: str) -> Optional[Tuple[int, str]]:
        for var in get_text_variants(text):
            norm = normalize_lyric_line(var)
            if norm in self.normalized_map:
                return self.normalized_map[norm]
        return None

    def _match_fuzzy_single(self, text: str, cutoff: float = 0.75) -> Optional[Tuple[int, str]]:
        for var in get_text_variants(text):
            norm = normalize_lyric_line(var)
            if not norm:
                continue
            matches = difflib.get_close_matches(norm, self.normalized_keys, n=1, cutoff=cutoff)
            if matches:
                return self.normalized_map[matches[0]]
        return None

    def match(self, ytm_line: str, cutoff: float = 0.65) -> Optional[str]:
        """
        Encontra a tradução para a linha do YouTube Music.
        1. Se for instrumental (♪), retorna (♪).
        2. Tenta correspondência exata da frase completa.
        3. Se não encontrar, separa por espaços em palavras/trechos:
           - Para cada trecho busca a chave correspondente.
           - Se uma parte não for encontrada mas há uma chave adjacente não chamada (ex: 飛翔いたら ao lado de 戻らないと言って),
             chama a chave não chamada automaticamente (evita pular o primeiro verso!).
        4. Checa se múltiplas chaves do Letras estão contidas na linha.
        5. Busca aproximada (fuzzy) na linha inteira.
        6. Se a escrita estiver completamente diferente, usa a próxima chave sequencial não chamada.
        """
        if is_instrumental(ytm_line):
            return "(♪)"

        # 1. Linha inteira exata
        exact_full = self._match_exact_single(ytm_line)
        if exact_full:
            idx, trans = exact_full
            self.called_indices.add(idx)
            self.last_called_index = max(self.last_called_index, idx)
            return trans

        # 2. Separação por espaço (cada palavra ou sub-frase)
        parts = [p.strip() for p in re.split(r"[\s\u3000]+", ytm_line) if p.strip()]
        part_matches: List[Optional[Tuple[int, str]]] = []

        if len(parts) > 1:
            for p in parts:
                m = self._match_exact_single(p) or self._match_fuzzy_single(p, cutoff=0.75)
                part_matches.append(m)

            # RESOLUÇÃO DE CHAVES NÃO CHAMADAS:
            # Caso uma parte não tenha sido encontrada por escrita diferente,
            # mas há uma chave não chamada adjacente no Letras.mus.br, utiliza-a!
            for i in range(len(part_matches)):
                if part_matches[i] is None:
                    # 1. Tenta pegar a chave anterior ao próximo verso que foi encontrado (K - 1)
                    if i + 1 < len(part_matches) and part_matches[i + 1] is not None:
                        target_k = part_matches[i + 1][0] - 1
                        if target_k >= 0 and target_k not in self.called_indices and target_k < len(self.ordered_translations):
                            part_matches[i] = (target_k, self.ordered_translations[target_k])
                    # 2. Tenta pegar a chave posterior ao verso anterior (J + 1)
                    elif i - 1 >= 0 and part_matches[i - 1] is not None:
                        target_j = part_matches[i - 1][0] + 1
                        if target_j < len(self.ordered_translations) and target_j not in self.called_indices:
                            part_matches[i] = (target_j, self.ordered_translations[target_j])

            resolved = [m for m in part_matches if m is not None]
            if len(resolved) >= 2:
                for idx, _ in resolved:
                    self.called_indices.add(idx)
                    self.last_called_index = max(self.last_called_index, idx)
                # Garante ordenação cronológica dos versos na união
                resolved.sort(key=lambda x: x[0])
                return " / ".join([trans for _, trans in resolved])
            elif len(resolved) == 1:
                idx, trans = resolved[0]
                self.called_indices.add(idx)
                self.last_called_index = max(self.last_called_index, idx)
                return trans

        # 3. Busca por chaves do dicionário contidas na linha
        variants = get_text_variants(ytm_line)
        found_keys = []
        for var in variants:
            norm_var = normalize_lyric_line(var)
            for key in self.normalized_keys:
                if len(key) >= 3:
                    pos = norm_var.find(key)
                    if pos != -1:
                        idx, trans = self.normalized_map[key]
                        found_keys.append((pos, len(key), idx, trans))

        if found_keys:
            found_keys.sort(key=lambda x: (x[0], -x[1]))
            chosen: List[Tuple[int, str]] = []
            last_end = -1
            for pos, length, idx, trans in found_keys:
                if pos >= last_end and (idx, trans) not in chosen:
                    chosen.append((idx, trans))
                    last_end = pos + length

            if len(chosen) >= 2:
                for idx, _ in chosen:
                    self.called_indices.add(idx)
                    self.last_called_index = max(self.last_called_index, idx)
                chosen.sort(key=lambda x: x[0])
                return " / ".join([trans for _, trans in chosen])
            elif len(chosen) == 1:
                idx, trans = chosen[0]
                self.called_indices.add(idx)
                self.last_called_index = max(self.last_called_index, idx)
                return trans

        # 4. Busca aproximada (fuzzy) na linha completa
        fuzzy_full = self._match_fuzzy_single(ytm_line, cutoff=cutoff)
        if fuzzy_full:
            idx, trans = fuzzy_full
            self.called_indices.add(idx)
            self.last_called_index = max(self.last_called_index, idx)
            return trans

        # 5. Fallback sequencial para versos não chamados se a escrita for 100% diferente
        next_uncalled = self.last_called_index + 1
        while next_uncalled in self.called_indices:
            next_uncalled += 1

        if next_uncalled < len(self.ordered_translations):
            self.called_indices.add(next_uncalled)
            self.last_called_index = next_uncalled
            return self.ordered_translations[next_uncalled]

        return None
