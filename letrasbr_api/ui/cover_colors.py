"""Tema dinâmico: extrai da capa do álbum uma paleta legível (fundo escuro, texto claro e destaque vibrante)."""

from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage

HUE_BUCKETS = 12


def dominant_vibrant_color(image: QImage) -> Optional[QColor]:
    """Cor vibrante dominante: agrupa pixels por tom, ponderando saturação e brilho. None para capas acinzentadas."""
    small = image.scaled(32, 32, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    buckets = [[0.0, 0.0, 0.0, 0.0] for _ in range(HUE_BUCKETS)]  # peso, r, g, b
    for y in range(small.height()):
        for x in range(small.width()):
            c = small.pixelColor(x, y)
            h, s, v = c.hsvHueF(), c.hsvSaturationF(), c.valueF()
            if h < 0 or s < 0.25 or v < 0.2:
                continue  # cinzas, pretos e brancos não definem a cor da capa
            weight = s * v
            bucket = buckets[int(h * HUE_BUCKETS) % HUE_BUCKETS]
            bucket[0] += weight
            bucket[1] += c.redF() * weight
            bucket[2] += c.greenF() * weight
            bucket[3] += c.blueF() * weight

    weight, r, g, b = max(buckets, key=lambda bk: bk[0])
    if weight < 1.0:  # pouquíssimos pixels coloridos
        return None
    return QColor.fromRgbF(r / weight, g / weight, b / weight)


def theme_from_cover(image_bytes: bytes) -> Optional[Dict[str, str]]:
    """Gera bgColor/origColor/transColor a partir dos bytes da capa (JPEG/PNG). None se não der para extrair."""
    image = QImage.fromData(image_bytes)
    if image.isNull():
        return None
    base = dominant_vibrant_color(image)
    if base is None:
        return None
    hue = base.hsvHueF()
    sat = base.hsvSaturationF()
    return {
        "bgColor": QColor.fromHsvF(hue, min(sat, 0.55) * 0.6, 0.11).name(),
        "origColor": QColor.fromHsvF(hue, 0.08, 0.90).name(),
        "transColor": QColor.fromHsvF(hue, max(sat, 0.55), 0.97).name(),
    }
