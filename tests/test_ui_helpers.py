"""Testes das partes da interface que não precisam de janela: paleta e cores da capa."""

import pytest
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QColor, QImage

from letrasbr_api.ui.cover_colors import theme_from_cover
from letrasbr_api.ui.palette import Palette, blend, luminance


def image_bytes(fill: str, accent: str = None) -> bytes:
    """PNG 40x40 de uma cor, com um quadrado de outra cor no meio (opcional)."""
    image = QImage(40, 40, QImage.Format_RGB32)
    image.fill(QColor(fill))
    if accent:
        for x in range(10, 30):
            for y in range(10, 30):
                image.setPixelColor(x, y, QColor(accent))
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def test_cover_theme_follows_vibrant_color():
    theme = theme_from_cover(image_bytes("#101010", accent="#e11d48"))  # capa escura com vermelho vivo
    accent = QColor(theme["transColor"])
    assert abs(accent.hsvHueF() - QColor("#e11d48").hsvHueF()) < 0.05
    assert luminance(theme["bgColor"]) < 0.1        # fundo escuro
    assert luminance(theme["origColor"]) > 0.6      # texto claro e legível


def test_black_and_white_cover_with_small_colored_detail_stays_black_and_white():
    image = QImage(QImage.fromData(image_bytes("#f0f0f0", accent="#202020")))
    for x in range(2):
        for y in range(2):
            image.setPixelColor(x, y, QColor("#e11d48"))  # selo vermelho minúsculo no canto
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    assert theme_from_cover(bytes(data))["transColor"] == "#ffffff"


def test_black_and_white_cover_gets_black_and_white_theme():
    theme = theme_from_cover(image_bytes("#808080", accent="#202020"))
    assert theme == {"bgColor": "#0d0d0d", "origColor": "#b3b3b3", "transColor": "#ffffff"}


def test_invalid_image_has_no_theme():
    assert theme_from_cover(b"not an image") is None


@pytest.mark.parametrize("bg, light", [("#121216", False), ("#f8fafc", True)])
def test_palette_adapts_to_light_and_dark(bg, light):
    pal = Palette.from_config({"bgColor": bg, "origColor": "#334155" if light else "#cbd5e1", "transColor": "#0284c7"})
    assert pal.is_light is light
    # Texto secundário fica entre o texto e o fundo (legível nos dois casos)
    assert min(luminance(pal.text), luminance(bg)) <= luminance(pal.muted) <= max(luminance(pal.text), luminance(bg))


def test_blend():
    assert blend("#ffffff", "#000000", 0.5) == "#808080"
    assert blend("#ff0000", "#0000ff", 1.0) == "#ff0000"
