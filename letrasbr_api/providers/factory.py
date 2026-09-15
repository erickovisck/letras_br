from typing import Dict, Optional
from providers.base import MusicProviderAdapter
from providers.ytmusic import YouTubeMusicAdapter
from providers.spotify import SpotifyAdapter


class ProviderFactory:
    """
    Fábrica e registro central de adapters de serviços de música.
    Gerencia instâncias únicas de cada adaptador e resolve o provedor adequado
    com base no identificador 'source'.
    """

    _registry: Dict[str, MusicProviderAdapter] = {}
    _initialized: bool = False

    @classmethod
    def _initialize_defaults(cls):
        if not cls._initialized:
            cls._registry["ytmusic"] = YouTubeMusicAdapter()
            cls._registry["spotify"] = SpotifyAdapter()
            cls._initialized = True

    @classmethod
    def register_provider(cls, name: str, adapter: MusicProviderAdapter):
        """Registra ou substitui um adaptador customizado."""
        cls._initialize_defaults()
        cls._registry[name.lower().strip()] = adapter

    @classmethod
    def get_provider(cls, source: Optional[str] = None) -> MusicProviderAdapter:
        """
        Retorna o adaptador adequado.
        Se 'source' for nulo ou vazio, adota 'ytmusic' como padrão garantindo
        retrocompatibilidade com clientes antigos.
        """
        cls._initialize_defaults()

        if not source:
            source = "ytmusic"

        normalized = source.lower().strip()
        if normalized in ["youtube", "ytm", "ytmusic", "youtubemusic"]:
            normalized = "ytmusic"
        elif normalized in ["spotify", "spot"]:
            normalized = "spotify"

        adapter = cls._registry.get(normalized)
        if not adapter:
            print(f"[FACTORY] ⚠️ Provedor '{source}' não reconhecido. Usando 'ytmusic' como fallback.")
            adapter = cls._registry.get("ytmusic")

        return adapter
