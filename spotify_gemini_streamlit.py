import os
import json
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

import streamlit as st
from streamlit_option_menu import option_menu
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import base64
from PIL import Image
import requests
from io import BytesIO

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuração da página Streamlit
st.set_page_config(
    page_title="Spotify Insights AI",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1DB954;
        text-align: center;
        margin-bottom: 1rem;
        font-weight: bold;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #FFFFFF;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    .card {
        background-color: #121212;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #1DB954;
        margin-bottom: 1rem;
    }
    .track-card {
        background-color: #181818;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 0.5rem;
        transition: transform 0.2s;
    }
    .track-card:hover {
        transform: translateY(-2px);
        background-color: #282828;
    }
    .insight-box {
        background: linear-gradient(135deg, #1DB954 0%, #191414 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1rem;
    }
    .stButton > button {
        background-color: #1DB954;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        font-weight: bold;
    }
    .stButton > button:hover {
        background-color: #1ED760;
    }
    .spotify-green {
        color: #1DB954;
    }
</style>
""", unsafe_allow_html=True)

# ========== ENCODER JSON PERSONALIZADO ==========

class EnhancedJSONEncoder(json.JSONEncoder):
    """Encoder JSON que lida com objetos customizados e datetime"""
    
    def default(self, obj):
        # Para objetos SpotifyTrack
        if isinstance(obj, SpotifyTrack):
            return obj.to_dict()
        
        # Para qualquer objeto com método to_dict
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        
        # Para datetime
        if isinstance(obj, datetime):
            return obj.isoformat()
        
        # Para outros tipos
        try:
            return super().default(obj)
        except (TypeError, ValueError):
            return str(obj)

def safe_serialize(obj):
    """
    Serializa objetos de forma recursiva e segura para JSON
    """
    if isinstance(obj, SpotifyTrack):
        return obj.to_dict()
    
    elif hasattr(obj, 'to_dict'):
        return obj.to_dict()
    
    elif isinstance(obj, datetime):
        return obj.isoformat()
    
    elif isinstance(obj, (list, tuple, set)):
        return [safe_serialize(item) for item in obj]
    
    elif isinstance(obj, dict):
        return {key: safe_serialize(value) for key, value in obj.items()}
    
    else:
        # Testa se é serializável nativamente
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            # Fallback para string
            return str(obj)

# ========== CLASSE SPOTIFYTRACK ==========

@dataclass
class SpotifyTrack:
    """Classe para representar uma música do Spotify"""
    name: str
    artist: str
    album: str
    duration_ms: int
    popularity: int
    image_url: Optional[str] = None
    played_at: Optional[str] = None
    is_playing: bool = False
    
    @property
    def duration_minutes(self) -> str:
        """Retorna a duração em formato MM:SS"""
        minutes = self.duration_ms // 60000
        seconds = (self.duration_ms % 60000) // 1000
        return f"{minutes}:{seconds:02d}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário serializável para JSON"""
        return {
            "name": self.name,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration_minutes,
            "duration_ms": self.duration_ms,
            "popularity": self.popularity,
            "image_url": self.image_url,
            "played_at": self.played_at,
            "is_playing": self.is_playing
        }

# ========== CLASSE PRINCIPAL ==========

class SpotifyGeminiAssistant:
    """Classe principal para integração Spotify + Gemini"""
    
    def __init__(self):
        """Inicializa o assistente com as APIs do Spotify e Gemini"""
        
        # Configurar Gemini
        gemini_api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
        if not gemini_api_key:
            st.error("GEMINI_API_KEY não encontrada. Configure no Streamlit Secrets ou variável de ambiente.")
            st.stop()
        
        genai.configure(api_key=gemini_api_key)
        
        # Configurar modelo Gemini
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Inicializar modelo Gemini
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        # Configurar Spotify
        self._setup_spotify()
        
        logger.info("SpotifyGeminiAssistant inicializado com sucesso!")
    
    def _setup_spotify(self):
        """Configura a autenticação do Spotify"""
        try:
            # Obter credenciais do Streamlit Secrets ou variáveis de ambiente
            client_id = st.secrets.get("SPOTIFY_CLIENT_ID", os.getenv("SPOTIFY_CLIENT_ID"))
            client_secret = st.secrets.get("SPOTIFY_CLIENT_SECRET", os.getenv("SPOTIFY_CLIENT_SECRET"))
            redirect_uri = st.secrets.get("SPOTIFY_REDIRECT_URI", os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8501"))
            
            if not client_id or not client_secret:
                st.error("Credenciais do Spotify não encontradas. Configure SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET.")
                st.stop()
            
            # Escopos necessários
            scope = " ".join([
                "user-top-read",
                "user-read-recently-played",
                "user-read-currently-playing",
                "user-read-playback-state",
                "user-library-read",
                "user-read-private"
            ])
            
            # Configurar autenticação OAuth
            auth_manager = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=scope,
                cache_path=".spotify_cache",
                show_dialog=True
            )
            
            self.sp = spotipy.Spotify(auth_manager=auth_manager)
            
            # Testar conexão
            user = self.sp.current_user()
            st.session_state.user_name = user['display_name']
            st.session_state.user_id = user['id']
            
            # Salvar informações do usuário
            if 'images' in user and user['images']:
                st.session_state.user_image = user['images'][0]['url']
            
            logger.info(f"Conectado ao Spotify como: {user['display_name']}")
            
        except Exception as e:
            logger.error(f"Erro ao configurar Spotify: {e}")
            st.error(f"Erro de autenticação: {str(e)}")
            st.info("Por favor, autentique-se com o Spotify.")
            st.stop()
    
    def get_top_tracks(self, limit: int = 10, time_range: str = "medium_term") -> Dict[str, Any]:
        """Obtém as músicas mais ouvidas do usuário"""
        try:
            results = self.sp.current_user_top_tracks(
                limit=limit,
                time_range=time_range
            )
            
            tracks = []
            for item in results['items']:
                track = SpotifyTrack(
                    name=item['name'],
                    artist=item['artists'][0]['name'],
                    album=item['album']['name'],
                    duration_ms=item['duration_ms'],
                    popularity=item['popularity'],
                    image_url=item['album']['images'][0]['url'] if item['album']['images'] else None
                )
                tracks.append(track.to_dict())  # Já converte para dicionário aqui!
            
            return {
                "status": "success",
                "data": tracks,  # Agora é lista de dicionários
                "metadata": {
                    "time_range": time_range,
                    "total": len(tracks)
                }
            }
        
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_top_artists(self, limit: int = 10, time_range: str = "medium_term") -> Dict[str, Any]:
        """Obtém os artistas mais ouvidos do usuário"""
        try:
            results = self.sp.current_user_top_artists(
                limit=limit,
                time_range=time_range
            )
            
            artists = []
            for item in results['items']:
                artists.append({
                    "name": item['name'],
                    "genres": item['genres'][:3],  # Limita a 3 gêneros
                    "popularity": item['popularity'],
                    "followers": item['followers']['total'],
                    "image_url": item['images'][0]['url'] if item['images'] else None
                })
            
            return {
                "status": "success",
                "data": artists,  # Já é lista de dicionários
                "metadata": {
                    "time_range": time_range,
                    "total": len(artists)
                }
            }
        
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_recently_played(self, limit: int = 20) -> Dict[str, Any]:
        """Obtém as músicas ouvidas recentemente"""
        try:
            results = self.sp.current_user_recently_played(limit=limit)
            
            tracks = []
            for item in results['items']:
                track_data = item['track']
                played_at = item.get('played_at', '')
                
                # Formatar data/hora
                if played_at:
                    dt = datetime.fromisoformat(played_at.replace('Z', '+00:00'))
                    played_at = dt.strftime("%d/%m/%Y %H:%M")
                
                track = SpotifyTrack(
                    name=track_data['name'],
                    artist=track_data['artists'][0]['name'],
                    album=track_data['album']['name'],
                    duration_ms=track_data['duration_ms'],
                    popularity=track_data['popularity'],
                    image_url=track_data['album']['images'][0]['url'] if track_data['album']['images'] else None,
                    played_at=played_at
                )
                tracks.append(track.to_dict())  # Converte para dicionário!
            
            return {
                "status": "success",
                "data": tracks,  # Lista de dicionários
                "metadata": {
                    "total": len(tracks)
                }
            }
        
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_currently_playing(self) -> Dict[str, Any]:
        """Obtém a música que está tocando no momento"""
        try:
            current = self.sp.currently_playing()
            
            if current is None or not current['is_playing']:
                return {
                    "status": "success",
                    "data": None,
                    "message": "Nenhuma música está tocando no momento"
                }
            
            item = current['item']
            progress_ms = current['progress_ms']
            
            # Calcular progresso percentual
            progress_percent = (progress_ms / item['duration_ms']) * 100 if item['duration_ms'] > 0 else 0
            
            track = SpotifyTrack(
                name=item['name'],
                artist=item['artists'][0]['name'],
                album=item['album']['name'],
                duration_ms=item['duration_ms'],
                popularity=item['popularity'],
                image_url=item['album']['images'][0]['url'] if item['album']['images'] else None,
                is_playing=True
            )
            
            track_dict = track.to_dict()  # Converte para dicionário
            track_dict.update({
                "progress_ms": progress_ms,
                "progress_percent": round(progress_percent, 1),
                "is_playing": True,
                "image_url": track.image_url
            })
            
            return {
                "status": "success",
                "data": track_dict  # Já é dicionário
            }
        
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_user_profile(self) -> Dict[str, Any]:
        """Obtém informações do perfil do usuário"""
        try:
            user = self.sp.current_user()
            
            return {
                "status": "success",
                "data": {
                    "display_name": user.get('display_name', ''),
                    "email": user.get('email', ''),
                    "country": user.get('country', ''),
                    "followers": user.get('followers', {}).get('total', 0),
                    "product": user.get('product', ''),
                    "image_url": user.get('images', [{}])[0].get('url', '') if user.get('images') else ''
                }
            }
        
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_playlists(self, limit: int = 20) -> Dict[str, Any]:
        """Obtém as playlists do usuário"""
        try:
            results = self.sp.current_user_playlists(limit=limit)
            
            playlists = []
            for item in results['items']:
                playlists.append({
                    "name": item['name'],
                    "description": item.get('description', ''),
                    "tracks": item['tracks']['total'],
                    "image_url": item['images'][0]['url'] if item['images'] else None
                })
            
            return {
                "status": "success",
                "data": playlists,
                "metadata": {
                    "total": len(playlists)
                }
            }
        
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def analyze_with_gemini(self, query: str, context_data: Dict[str, Any]) -> str:
        """Analisa dados com Gemini"""
        try:
            # Garantir que todos os dados sejam serializáveis
            serialized_context = safe_serialize(context_data)
            
            # Usar o encoder personalizado para garantir serialização correta
            context_json = json.dumps(
                serialized_context, 
                indent=2, 
                ensure_ascii=False,
                cls=EnhancedJSONEncoder
            )
            
            prompt = f"""
            Como especialista em análise musical, analise os dados do Spotify fornecidos e responda à pergunta do usuário.
            
            PERGUNTA DO USUÁRIO: {query}
            
            DADOS DISPONÍVEIS:
            {context_json}
            
            Instruções:
            1. Seja conciso mas informativo
            2. Destaque padrões interessantes
            3. Ofereça insights pessoais
            4. Sugira recomendações quando apropriado
            5. Use um tom amigável e entusiástico
            
            RESPOSTA:
            """
            
            response = self.model.generate_content(prompt)
            return response.text
        
        except Exception as e:
            logger.error(f"Erro ao processar com Gemini: {e}")
            return f"Erro ao processar com Gemini: {str(e)}"
    
    def get_statistics_summary(self) -> Dict[str, Any]:
        """Obtém um resumo das estatísticas do usuário"""
        summary = {}
        
        try:
            # Obter dados de várias fontes
            summary["top_tracks_short"] = self.get_top_tracks(limit=5, time_range="short_term")
            summary["top_artists_short"] = self.get_top_artists(limit=5, time_range="short_term")
            summary["recently_played"] = self.get_recently_played(limit=10)
            summary["currently_playing"] = self.get_currently_playing()
            
            return {
                "status": "success",
                "summary": summary
            }
        
        except Exception as e:
            return {"status": "error", "message": str(e)}

# ========== FUNÇÕES DE EXIBIÇÃO ==========

def display_track(track_dict, show_album=True, show_popularity=True):
    """Exibe um cartão de música a partir de um dicionário"""
    with st.container():
        col1, col2, col3 = st.columns([1, 6, 1])
        
        with col1:
            if track_dict.get('image_url'):
                try:
                    response = requests.get(track_dict['image_url'])
                    img = Image.open(BytesIO(response.content))
                    st.image(img, width=50)
                except:
                    st.image("🎵", width=50)
            else:
                st.image("🎵", width=50)
        
        with col2:
            st.markdown(f"**{track_dict['name']}**")
            st.markdown(f"*{track_dict['artist']}*", help=track_dict.get('album', '') if show_album else "")
            
            if track_dict.get('played_at'):
                st.caption(f"🎧 Ouvido em: {track_dict['played_at']}")
        
        with col3:
            if show_popularity and 'popularity' in track_dict:
                st.progress(track_dict['popularity'] / 100)
                st.caption(f"{track_dict['popularity']}%")
        
        st.markdown("---")

def display_track_obj(track, show_album=True, show_popularity=True):
    """Exibe um cartão de música a partir de um objeto SpotifyTrack"""
    with st.container():
        col1, col2, col3 = st.columns([1, 6, 1])
        
        with col1:
            if track.image_url:
                try:
                    response = requests.get(track.image_url)
                    img = Image.open(BytesIO(response.content))
                    st.image(img, width=50)
                except:
                    st.image("🎵", width=50)
            else:
                st.image("🎵", width=50)
        
        with col2:
            st.markdown(f"**{track.name}**")
            st.markdown(f"*{track.artist}*", help=track.album if show_album else "")
            
            if track.played_at:
                st.caption(f"🎧 Ouvido em: {track.played_at}")
        
        with col3:
            if show_popularity:
                st.progress(track.popularity / 100)
                st.caption(f"{track.popularity}%")
        
        st.markdown("---")

def display_artist(artist):
    """Exibe um cartão de artista"""
    with st.container():
        col1, col2 = st.columns([1, 4])
        
        with col1:
            if artist.get('image_url'):
                try:
                    response = requests.get(artist['image_url'])
                    img = Image.open(BytesIO(response.content))
                    st.image(img, width=60)
                except:
                    st.image("👨‍🎤", width=60)
            else:
                st.image("👨‍🎤", width=60)
        
        with col2:
            st.markdown(f"**{artist['name']}**")
            if artist.get('genres'):
                st.caption(f"🎶 {', '.join(artist['genres'])}")
            
            col_metrics = st.columns(2)
            with col_metrics[0]:
                st.metric("Popularidade", f"{artist['popularity']}%")
            with col_metrics[1]:
                st.metric("Seguidores", f"{artist['followers']:,}")
        
        st.markdown("---")

def create_popularity_chart(tracks_dicts):
    """Cria gráfico de popularidade das músicas a partir de dicionários"""
    if not tracks_dicts:
        return
    
    df = pd.DataFrame([{
        'Música': t['name'][:20] + '...' if len(t['name']) > 20 else t['name'],
        'Artista': t['artist'][:15] + '...' if len(t['artist']) > 15 else t['artist'],
        'Popularidade': t['popularity']
    } for t in tracks_dicts])
    
    fig = px.bar(df, x='Música', y='Popularidade', 
                 color='Popularidade',
                 title="Popularidade das Músicas",
                 hover_data=['Artista'],
                 color_continuous_scale='Viridis')
    
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        xaxis_tickangle=-45
    )
    
    st.plotly_chart(fig, use_container_width=True)

# ========== FUNÇÕES PRINCIPAIS ==========

def main():
    """Função principal da aplicação Streamlit"""
    
    # Título principal
    st.markdown('<h1 class="main-header">🎵 Spotify Insights AI</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #B3B3B3;">Analise seus hábitos musicais com IA</p>', unsafe_allow_html=True)
    
    # Inicializar sessão
    if 'assistant' not in st.session_state:
        try:
            with st.spinner("🔗 Conectando ao Spotify e Gemini..."):
                st.session_state.assistant = SpotifyGeminiAssistant()
                st.success("✅ Conexões estabelecidas!")
        except Exception as e:
            st.error(f"❌ Erro ao inicializar: {str(e)}")
            return
    
    assistant = st.session_state.assistant
    
    # Sidebar com menu
    with st.sidebar:
        # Informações do usuário
        st.markdown("### 👤 Perfil")
        if 'user_name' in st.session_state:
            col_user = st.columns([1, 3])
            with col_user[0]:
                if 'user_image' in st.session_state and st.session_state.user_image:
                    try:
                        response = requests.get(st.session_state.user_image)
                        img = Image.open(BytesIO(response.content))
                        st.image(img, width=40)
                    except:
                        st.image("👤", width=40)
                else:
                    st.image("👤", width=40)
            
            with col_user[1]:
                st.write(f"**{st.session_state.user_name}**")
        
        st.markdown("---")
        
        # Menu de navegação
        menu = option_menu(
            menu_title="📊 Menu",
            options=["Dashboard", "Top Músicas", "Top Artistas", "Histórico", "Playlists", "Chat AI"],
            icons=["house", "music-note", "person", "clock", "list", "robot"],
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "#121212"},
                "icon": {"color": "#1DB954", "font-size": "20px"},
                "nav-link": {
                    "font-size": "16px",
                    "text-align": "left",
                    "margin": "0px",
                    "--hover-color": "#1DB954",
                    "color": "white"
                },
                "nav-link-selected": {"background-color": "#1DB954"},
            }
        )
        
        st.markdown("---")
        
        # Configurações
        st.markdown("### ⚙️ Configurações")
        time_range = st.selectbox(
            "Período de análise:",
            ["short_term (4 semanas)", "medium_term (6 meses)", "long_term (vários anos)"],
            index=1
        )
        
        time_map = {
            "short_term (4 semanas)": "short_term",
            "medium_term (6 meses)": "medium_term",
            "long_term (vários anos)": "long_term"
        }
        
        selected_time = time_map[time_range]
        
        st.markdown("---")
        
        # Estatísticas rápidas
        st.markdown("### 📈 Status")
        try:
            current = assistant.get_currently_playing()
            if current["status"] == "success" and current["data"]:
                st.markdown("🎶 **Tocando agora:**")
                track = current["data"]
                st.write(f"**{track['name'][:20]}...**")
                st.write(f"*{track['artist'][:20]}...*")
            else:
                st.markdown("🔇 **Nada tocando**")
        except:
            pass
    
    # Conteúdo principal baseado no menu selecionado
    if menu == "Dashboard":
        display_dashboard(assistant, selected_time)
    elif menu == "Top Músicas":
        display_top_tracks(assistant, selected_time)
    elif menu == "Top Artistas":
        display_top_artists(assistant, selected_time)
    elif menu == "Histórico":
        display_recent_history(assistant)
    elif menu == "Playlists":
        display_playlists(assistant)
    elif menu == "Chat AI":
        display_chat_ai(assistant)

def display_dashboard(assistant, time_range):
    """Exibe o dashboard principal"""
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 🎵 Top Músicas")
        tracks = assistant.get_top_tracks(limit=5, time_range=time_range)
        if tracks["status"] == "success":
            for i, track in enumerate(tracks["data"][:5], 1):
                st.write(f"{i}. **{track['name'][:20]}...**")
                st.caption(f"*{track['artist'][:15]}...*")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 👨‍🎤 Top Artistas")
        artists = assistant.get_top_artists(limit=5, time_range=time_range)
        if artists["status"] == "success":
            for i, artist in enumerate(artists["data"][:5], 1):
                st.write(f"{i}. **{artist['name'][:20]}...**")
                if artist['genres']:
                    st.caption(f"🎶 {artist['genres'][0]}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### ⏱️ Agora")
        current = assistant.get_currently_playing()
        if current["status"] == "success" and current["data"]:
            track = current["data"]
            st.write(f"**{track['name'][:25]}...**")
            st.write(f"*{track['artist'][:20]}...*")
            st.progress(track['progress_percent'] / 100)
            st.caption(f"{track['progress_percent']}% concluído")
        else:
            st.write("Nada tocando no momento")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Gráficos
    st.markdown("---")
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        tracks = assistant.get_top_tracks(limit=10, time_range=time_range)
        if tracks["status"] == "success":
            create_popularity_chart(tracks["data"])
    
    with col_chart2:
        artists = assistant.get_top_artists(limit=10, time_range=time_range)
        if artists["status"] == "success":
            df = pd.DataFrame([{
                'Artista': a['name'][:15] + '...' if len(a['name']) > 15 else a['name'],
                'Popularidade': a['popularity'],
                'Seguidores': a['followers']
            } for a in artists["data"]])
            
            fig = px.scatter(df, x='Popularidade', y='Seguidores',
                            size='Popularidade', color='Artista',
                            title="Artistas: Popularidade vs Seguidores",
                            hover_name='Artista')
            
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_color='white'
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # Insights gerados por IA
    st.markdown("---")
    st.markdown('<h3 class="sub-header">🤖 Insights de IA</h3>', unsafe_allow_html=True)
    
    if st.button("🔍 Gerar Análise Personalizada", use_container_width=True):
        with st.spinner("Analisando seus dados musicais..."):
            # Coletar dados para análise
            data = {
                "top_tracks": assistant.get_top_tracks(limit=10, time_range=time_range),
                "top_artists": assistant.get_top_artists(limit=10, time_range=time_range),
                "recent_tracks": assistant.get_recently_played(limit=10)
            }
            
            # Gerar insights
            prompt = "Analise meus dados do Spotify e forneça insights interessantes sobre meus hábitos musicais."
            insights = assistant.analyze_with_gemini(prompt, data)
            
            st.markdown(f'<div class="insight-box">{insights}</div>', unsafe_allow_html=True)

def display_top_tracks(assistant, time_range):
    """Exibe top músicas"""
    st.markdown(f'<h3 class="sub-header">🎵 Suas Músicas Mais Ouvidas ({time_range})</h3>', unsafe_allow_html=True)
    
    limit = st.slider("Número de músicas:", 5, 50, 20)
    
    with st.spinner("Carregando suas músicas..."):
        tracks_result = assistant.get_top_tracks(limit=limit, time_range=time_range)
    
    if tracks_result["status"] == "success":
        tracks_data = tracks_result["data"]
        
        # Filtros
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            search = st.text_input("🔍 Buscar música ou artista:", "")
        
        with col_filter2:
            min_popularity = st.slider("Popularidade mínima:", 0, 100, 50)
        
        # Lista de músicas
        filtered_tracks = [
            t for t in tracks_data 
            if t['popularity'] >= min_popularity and
            (search.lower() in t['name'].lower() or search.lower() in t['artist'].lower())
        ]
        
        if filtered_tracks:
            # Exibir estatísticas
            avg_popularity = sum(t['popularity'] for t in filtered_tracks) / len(filtered_tracks)
            total_duration = sum(t['duration_ms'] for t in filtered_tracks) / 60000  # em minutos
            
            col_stats1, col_stats2, col_stats3 = st.columns(3)
            with col_stats1:
                st.metric("Total de Músicas", len(filtered_tracks))
            with col_stats2:
                st.metric("Popularidade Média", f"{avg_popularity:.1f}%")
            with col_stats3:
                st.metric("Duração Total", f"{total_duration:.0f} min")
            
            # Lista de músicas
            st.markdown("---")
            for i, track in enumerate(filtered_tracks, 1):
                display_track(track)
            
            # Opção para análise
            if st.button("📊 Analisar Essas Músicas com IA"):
                with st.spinner("Gerando análise..."):
                    analysis_data = {
                        "tracks": filtered_tracks,  # Já são dicionários
                        "statistics": {
                            "average_popularity": avg_popularity,
                            "total_tracks": len(filtered_tracks),
                            "time_range": time_range
                        }
                    }
                    
                    prompt = f"""
                    Analise essas {len(filtered_tracks)} músicas que o usuário mais ouviu.
                    Forneça insights sobre:
                    1. Padrões de gênero (se possível identificar)
                    2. Nível de popularidade das músicas
                    3. Possíveis mudanças no gosto musical
                    4. Recomendações baseadas nessas músicas
                    """
                    
                    analysis = assistant.analyze_with_gemini(prompt, analysis_data)
                    st.markdown(f'<div class="insight-box">{analysis}</div>', unsafe_allow_html=True)
        else:
            st.info("Nenhuma música encontrada com os filtros atuais.")
    else:
        st.error(f"Erro ao carregar músicas: {tracks_result.get('message')}")

def display_top_artists(assistant, time_range):
    """Exibe top artistas"""
    st.markdown(f'<h3 class="sub-header">👨‍🎤 Seus Artistas Mais Ouvidos ({time_range})</h3>', unsafe_allow_html=True)
    
    limit = st.slider("Número de artistas:", 5, 50, 20)
    
    with st.spinner("Carregando seus artistas..."):
        artists = assistant.get_top_artists(limit=limit, time_range=time_range)
    
    if artists["status"] == "success":
        # Filtros
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            search = st.text_input("🔍 Buscar artista:", "")
        
        with col_filter2:
            min_popularity = st.slider("Popularidade mínima:", 0, 100, 50)
        
        # Lista de artistas
        filtered_artists = [
            a for a in artists["data"] 
            if a['popularity'] >= min_popularity and
            search.lower() in a['name'].lower()
        ]
        
        if filtered_artists:
            # Exibir estatísticas
            avg_popularity = sum(a['popularity'] for a in filtered_artists) / len(filtered_artists)
            total_followers = sum(a['followers'] for a in filtered_artists)
            
            col_stats1, col_stats2 = st.columns(2)
            with col_stats1:
                st.metric("Total de Artistas", len(filtered_artists))
            with col_stats2:
                st.metric("Seguidores Totais", f"{total_followers:,}")
            
            # Análise de gêneros
            all_genres = []
            for artist in filtered_artists:
                all_genres.extend(artist['genres'])
            
            from collections import Counter
            genre_counts = Counter(all_genres)
            
            if genre_counts:
                top_genres = genre_counts.most_common(5)
                st.markdown("#### 🎶 Gêneros Mais Comuns")
                for genre, count in top_genres:
                    st.progress(count / len(filtered_artists))
                    st.caption(f"{genre}: {count} artistas")
            
            # Lista de artistas
            st.markdown("---")
            st.markdown("#### 🏆 Seus Artistas")
            for artist in filtered_artists:
                display_artist(artist)
            
            # Análise de IA
            if st.button("🤖 Analisar Meus Artistas com IA"):
                with st.spinner("Analisando padrões..."):
                    analysis_data = {
                        "artists": filtered_artists,
                        "genre_analysis": dict(genre_counts.most_common(10)),
                        "statistics": {
                            "average_popularity": avg_popularity,
                            "total_artists": len(filtered_artists),
                            "total_followers": total_followers
                        }
                    }
                    
                    prompt = """
                    Analise os artistas favoritos deste usuário e forneça insights sobre:
                    1. Padrões de gêneros musicais
                    2. Características comuns entre os artistas
                    3. Sugestões de artistas similares
                    4. Evolução do gosto musical baseado na popularidade
                    """
                    
                    analysis = assistant.analyze_with_gemini(prompt, analysis_data)
                    st.markdown(f'<div class="insight-box">{analysis}</div>', unsafe_allow_html=True)
        else:
            st.info("Nenhum artista encontrado com os filtros atuais.")
    else:
        st.error(f"Erro ao carregar artistas: {artists.get('message')}")

def display_recent_history(assistant):
    """Exibe histórico recente"""
    st.markdown('<h3 class="sub-header">🕐 Seu Histórico Recente</h3>', unsafe_allow_html=True)
    
    limit = st.slider("Número de reproduções recentes:", 10, 100, 30)
    
    with st.spinner("Carregando seu histórico..."):
        recent = assistant.get_recently_played(limit=limit)
    
    if recent["status"] == "success":
        if recent["data"]:
            # Análise temporal
            st.markdown("#### 📈 Atividade por Hora")
            
            # Extrair horas das reproduções
            hours = []
            for track in recent["data"]:
                if track.get('played_at'):
                    try:
                        hour = int(track['played_at'].split(" ")[1].split(":")[0])
                        hours.append(hour)
                    except:
                        pass
            
            if hours:
                hour_counts = {hour: hours.count(hour) for hour in range(24)}
                
                fig = go.Figure(data=[
                    go.Bar(x=list(hour_counts.keys()), y=list(hour_counts.values()),
                          marker_color='#1DB954')
                ])
                
                fig.update_layout(
                    title="Reproduções por Hora do Dia",
                    xaxis_title="Hora",
                    yaxis_title="Número de Reproduções",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='white'
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            # Lista de reproduções recentes
            st.markdown("---")
            st.markdown(f"#### 🎧 Últimas {len(recent['data'])} Reproduções")
            
            for track in recent["data"]:
                display_track(track, show_album=False, show_popularity=False)
            
            # Análise de IA
            if st.button("🧠 Obter Insights do Histórico"):
                with st.spinner("Analisando padrões de escuta..."):
                    analysis_data = {
                        "recent_tracks": recent["data"],
                        "hour_distribution": hour_counts if hours else {},
                        "total_tracks": len(recent["data"])
                    }
                    
                    prompt = """
                    Analise o histórico recente de reproduções e forneça insights sobre:
                    1. Padrões de horário de escuta
                    2. Variação de gêneros ao longo do tempo
                    3. Consistência nas escolhas musicais
                    4. Sugestões baseadas no histórico recente
                    """
                    
                    analysis = assistant.analyze_with_gemini(prompt, analysis_data)
                    st.markdown(f'<div class="insight-box">{analysis}</div>', unsafe_allow_html=True)
        else:
            st.info("Nenhuma reprodução recente encontrada.")
    else:
        st.error(f"Erro ao carregar histórico: {recent.get('message')}")

def display_playlists(assistant):
    """Exibe playlists do usuário"""
    st.markdown('<h3 class="sub-header">📋 Suas Playlists</h3>', unsafe_allow_html=True)
    
    with st.spinner("Carregando suas playlists..."):
        playlists = assistant.get_playlists(limit=50)
    
    if playlists["status"] == "success":
        if playlists["data"]:
            # Estatísticas
            total_tracks = sum(p['tracks'] for p in playlists["data"])
            avg_tracks = total_tracks / len(playlists["data"])
            
            col_stats1, col_stats2 = st.columns(2)
            with col_stats1:
                st.metric("Total de Playlists", len(playlists["data"]))
            with col_stats2:
                st.metric("Média de Músicas", f"{avg_tracks:.0f}")
            
            # Grid de playlists
            st.markdown("---")
            cols = st.columns(4)
            
            for idx, playlist in enumerate(playlists["data"]):
                with cols[idx % 4]:
                    with st.container():
                        # Imagem da playlist
                        if playlist['image_url']:
                            try:
                                response = requests.get(playlist['image_url'])
                                img = Image.open(BytesIO(response.content))
                                st.image(img, use_container_width=True)
                            except:
                                st.image("📋", use_container_width=True)
                        else:
                            st.image("📋", use_container_width=True)
                        
                        # Informações
                        st.write(f"**{playlist['name'][:20]}...**" if len(playlist['name']) > 20 else f"**{playlist['name']}**")
                        st.caption(f"{playlist['tracks']} músicas")
                        
                        if playlist['description']:
                            with st.expander("Descrição"):
                                st.write(playlist['description'])
            
            # Análise de IA
            if st.button("🎯 Analisar Minhas Playlists"):
                with st.spinner("Analisando coleção de playlists..."):
                    analysis_data = {
                        "playlists": playlists["data"],
                        "statistics": {
                            "total_playlists": len(playlists["data"]),
                            "total_tracks": total_tracks,
                            "average_tracks": avg_tracks
                        }
                    }
                    
                    prompt = """
                    Analise as playlists deste usuário e forneça insights sobre:
                    1. Diversidade de conteúdo (muitas playlists especializadas vs gerais)
                    2. Tamanho médio das playlists
                    3. Possíveis padrões nos nomes ou descrições
                    4. Sugestões para organização ou novas playlists
                    """
                    
                    analysis = assistant.analyze_with_gemini(prompt, analysis_data)
                    st.markdown(f'<div class="insight-box">{analysis}</div>', unsafe_allow_html=True)
        else:
            st.info("Nenhuma playlist encontrada.")
    else:
        st.error(f"Erro ao carregar playlists: {playlists.get('message')}")

def display_chat_ai(assistant):
    """Exibe interface de chat com IA"""
    st.markdown('<h3 class="sub-header">🤖 Chat Musical com IA</h3>', unsafe_allow_html=True)
    
    # Inicializar histórico de chat
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Exibir histórico de mensagens
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Input do usuário
    if prompt := st.chat_input("Pergunte sobre seus dados do Spotify..."):
        # Adicionar mensagem do usuário
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Processar com Gemini
        with st.chat_message("assistant"):
            with st.spinner("Analisando seus dados..."):
                # Coletar dados relevantes baseados na pergunta
                context_data = {}
                
                # Detectar tipo de pergunta
                question_lower = prompt.lower()
                
                # Obter dados serializados diretamente das funções
                if any(word in question_lower for word in ["música", "track", "canção", "song"]):
                    tracks_result = assistant.get_top_tracks(limit=20, time_range="medium_term")
                    if tracks_result["status"] == "success":
                        context_data["top_tracks"] = tracks_result["data"]
                
                if any(word in question_lower for word in ["artista", "banda", "artist", "cantor"]):
                    artists_result = assistant.get_top_artists(limit=20, time_range="medium_term")
                    if artists_result["status"] == "success":
                        context_data["top_artists"] = artists_result["data"]
                
                if any(word in question_lower for word in ["recente", "histórico", "history", "recent"]):
                    recent_result = assistant.get_recently_played(limit=20)
                    if recent_result["status"] == "success":
                        context_data["recent_tracks"] = recent_result["data"]
                
                if any(word in question_lower for word in ["tocando", "agora", "current", "playing"]):
                    current_result = assistant.get_currently_playing()
                    if current_result["status"] == "success":
                        context_data["current_track"] = current_result["data"]
                
                # Adicionar perfil se não houver contexto específico
                if not context_data:
                    profile_result = assistant.get_user_profile()
                    if profile_result["status"] == "success":
                        context_data["profile"] = profile_result["data"]
                    
                    tracks_result = assistant.get_top_tracks(limit=5, time_range="medium_term")
                    artists_result = assistant.get_top_artists(limit=5, time_range="medium_term")
                    
                    if tracks_result["status"] == "success" and artists_result["status"] == "success":
                        context_data["general_stats"] = {
                            "top_tracks": tracks_result["data"],
                            "top_artists": artists_result["data"]
                        }
                
                # Gerar resposta (a função analyze_with_gemini já serializa corretamente)
                response = assistant.analyze_with_gemini(prompt, context_data)
                st.markdown(response)
        
        # Adicionar resposta ao histórico
        st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Sugestões de perguntas
    st.markdown("---")
    st.markdown("#### 💡 Sugestões de Perguntas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🎵 Quais são minhas músicas mais ouvidas?"):
            st.chat_input("", value="Quais são minhas músicas mais ouvidas?")
            st.rerun()
        
        if st.button("👨‍🎤 Quem são meus artistas favoritos?"):
            st.chat_input("", value="Quem são meus artistas favoritos?")
            st.rerun()
    
    with col2:
        if st.button("🎯 Me dê recomendações musicais"):
            st.chat_input("", value="Me dê recomendações musicais baseadas no meu gosto")
            st.rerun()
        
        if st.button("📊 Analise meus hábitos de escuta"):
            st.chat_input("", value="Analise meus hábitos de escuta e me dê insights")
            st.rerun()

if __name__ == "__main__":
    main()