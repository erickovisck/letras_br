import pytest

from letrasbr_api import machine_translate, main, scraper, track_prefs, translation_logger


def pytest_addoption(parser):
    parser.addoption("--network", action="store_true", help="roda também os testes que acessam a internet")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--network"):
        return
    skip = pytest.mark.skip(reason="teste de rede (use --network)")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def isolate_side_effects(tmp_path, monkeypatch):
    """Nenhum teste grava no log, no cache ou na configuração reais do usuário."""
    monkeypatch.setattr(translation_logger, "LOG_FILE", str(tmp_path / "sem_traducao.log"))
    monkeypatch.setattr(translation_logger, "LOGS_DIR", str(tmp_path))
    monkeypatch.setattr(machine_translate, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(machine_translate, "CACHE_FILE", str(tmp_path / "cache" / "auto_translations.json"))
    monkeypatch.setattr(machine_translate, "_cache", None)
    monkeypatch.setattr(machine_translate, "_blocked_until", {})
    monkeypatch.setattr(main, "save_config", lambda cfg: None)
    monkeypatch.setattr(track_prefs, "PREFS_FILE", str(tmp_path / "track_prefs.json"))
    monkeypatch.setattr(track_prefs, "_prefs", None)
    scraper._translation_cache.clear()
    yield
    scraper._translation_cache.clear()
