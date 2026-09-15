from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class TimedLine:
    """Modelo canônico unificado de linha de letra temporizada."""
    start_time: int  # Tempo de início em milissegundos
    end_time: int    # Tempo de término em milissegundos
    text: str        # Texto original do verso


@dataclass
class TrackInfo:
    """Informações padronizadas sobre a faixa em reprodução."""
    title: str
    artist: str
    album: Optional[str] = None
    track_id: Optional[str] = None  # videoId (YouTube Music) ou track ID (Spotify)
    duration: Optional[float] = None
    source: str = "ytmusic"


class MusicProviderAdapter(ABC):
    """
    Interface alvo do Design Pattern Adapter para provedores de streaming de música.
    Define o contrato para obtenção de letras temporizadas e controle de reprodução.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Identificador exclusivo do provedor: 'ytmusic', 'spotify', etc."""
        pass

    @abstractmethod
    def get_timed_lyrics(self, track: TrackInfo) -> Optional[List[TimedLine]]:
        """
        Obtém as linhas de letra com timestamps sincronizados para a faixa fornecida.
        Retorna uma lista de TimedLine em milissegundos ou None se não encontrado.
        """
        pass

    @abstractmethod
    def queue_command(self, action: str) -> None:
        """
        Enfileira um comando de transporte (ex: 'play_pause', 'next', 'previous').
        """
        pass

    @abstractmethod
    def pop_pending_command(self) -> Optional[str]:
        """
        Consome e retorna o comando pendente para o player, se houver.
        """
        pass
