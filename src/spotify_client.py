"""Cliente para interação com a API do Spotify"""
import os
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st

logger = logging.getLogger(__name__)

@dataclass
class SpotifyTrack:
    name: str
    artist: str
    album: str
    duration_ms: int
    popularity: int
    image_url: Optional[str] = None
    played_at: Optional[str] = None
    
    @property
    def duration_minutes(self) -> str:
        minutes = self.duration_ms // 60000
        seconds = (self.duration_ms % 60000) // 1000
        return f"{minutes}:{seconds:02d}"

class SpotifyClient:
    def __init__(self):
        self._setup_client()
        
    def _setup_client(self):
        """Configura o cliente do Spotify"""
        try:
            self.client = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=st.secrets["SPOTIFY_CLIENT_ID"],
                client_secret=st.secrets["SPOTIFY_CLIENT_SECRET"],
                redirect_uri=st.secrets["SPOTIFY_REDIRECT_URI"],
                scope=" ".join([
                    "user-top-read",
                    "user-read-recently-played",
                    "user-read-currently-playing",
                    "user-read-playback-state",
                ]),
                cache_path=".spotify_cache"
            ))
            
            # Testar conexão
            user = self.client.current_user()
            st.session_state.spotify_user = user['display_name']
            logger.info(f"Conectado ao Spotify como: {user['display_name']}")
            
        except Exception as e:
            logger.error(f"Erro ao configurar Spotify: {e}")
            raise
    
    def get_user_profile(self) -> Dict:
        """Obtém perfil do usuário"""
        return self.client.current_user()
    
    # ... outros métodos do Spotify