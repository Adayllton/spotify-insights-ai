import os
import json
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from collections import Counter

import streamlit as st
from streamlit_option_menu import option_menu
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheHandler
import base64
from PIL import Image
import requests
from io import BytesIO

# ========== CACHE HANDLER PERSONALIZADO PARA STREAMLIT ==========

class StreamlitSessionCacheHandler(CacheHandler):
    """
    Salva o token na sessão do Streamlit para cada usuário individualmente,
    em vez de usar um arquivo no servidor.
    """
    
    def __init__(self):
        # Inicializa o cache na sessão se não existir
        if 'spotify_token' not in st.session_state:
            st.session_state.spotify_token = None
    
    def get_cached_token(self):
        """Retorna o token armazenado na sessão"""
        return st.session_state.spotify_token
    
    def save_token_to_cache(self, token_info):
        """Salva o token na sessão"""
        st.session_state.spotify_token = token_info
    
    def clear_token(self):
        """Limpa o token da sessão"""
        if 'spotify_token' in st.session_state:
            st.session_state.spotify_token = None

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    .feature-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1rem;
    }
    .era-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1rem;
    }
    .genre-card {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1rem;
    }
    .metric-high {
        color: #1DB954;
        font-weight: bold;
    }
    .metric-low {
        color: #FF6B6B;
        font-weight: bold;
    }
    .progress-ring {
        width: 100px;
        height: 100px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: conic-gradient(#1DB954 var(--progress), #333 0%);
        margin: 0 auto;
    }
    .progress-ring-inner {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        background: #121212;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        color: white;
    }
    .login-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 70vh;
        text-align: center;
    }
    .login-button {
        background-color: #1DB954;
        color: white;
        padding: 15px 30px;
        border-radius: 30px;
        text-decoration: none;
        font-weight: bold;
        font-size: 18px;
        display: inline-block;
        margin: 20px 0;
        border: none;
        cursor: pointer;
    }
    .login-button:hover {
        background-color: #1ED760;
        transform: scale(1.05);
        transition: all 0.3s ease;
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

# ========== CLASSE SPOTIFYTRACK ATUALIZADA ==========

@dataclass
class SpotifyTrack:
    """Classe para representar uma música do Spotify"""
    id: str
    name: str
    artist: str
    album: str
    duration_ms: int
    popularity: int
    release_date: Optional[str] = None
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
            "id": self.id,
            "name": self.name,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration_minutes,
            "duration_ms": self.duration_ms,
            "popularity": self.popularity,
            "release_date": self.release_date,
            "image_url": self.image_url,
            "played_at": self.played_at,
            "is_playing": self.is_playing
        }

# ========== CLASSE PRINCIPAL CORRIGIDA ==========

class SpotifyGeminiAssistant:
    """Classe principal para integração Spotify + Gemini (Multi-Usuário)"""
    
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
            model_name="gemini-2.5-flash",
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        # Configurar Spotify (agora multi-usuário)
        self._setup_spotify()
        
        logger.info("SpotifyGeminiAssistant inicializado com sucesso!")
    
    def _setup_spotify(self):
        """Configura a autenticação do Spotify com cache por sessão"""
        try:
            # Obter credenciais do Streamlit Secrets ou variáveis de ambiente
            client_id = st.secrets.get("SPOTIFY_CLIENT_ID", os.getenv("SPOTIFY_CLIENT_ID"))
            client_secret = st.secrets.get("SPOTIFY_CLIENT_SECRET", os.getenv("SPOTIFY_CLIENT_SECRET"))
            redirect_uri = st.secrets.get("SPOTIFY_REDIRECT_URI", os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8501"))
            
            if not client_id or not client_secret:
                st.error("Credenciais do Spotify não encontradas. Configure SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET.")
                st.stop()
            
            # IMPORTANTE: Remover a barra final se existir
            if redirect_uri.endswith('/'):
                redirect_uri = redirect_uri[:-1]
            
            # Escopos necessários
            scope = " ".join([
                "user-top-read",
                "user-read-recently-played",
                "user-read-currently-playing",
                "user-read-playback-state",
                "user-library-read",
                "user-read-private"
            ])
            
            # Inicializar o cache handler da sessão
            cache_handler = StreamlitSessionCacheHandler()
            
            # Configurar autenticação OAuth
            auth_manager = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=scope,
                cache_handler=cache_handler,  # Usa nosso cache handler personalizado
                show_dialog=True
            )
            
            # 1. Verifica se estamos voltando do login do Spotify (tem 'code' na URL?)
            # Usar st.experimental_get_query_params para compatibilidade
            params = st.experimental_get_query_params()
            
            if "code" in params:
                try:
                    code = params["code"][0]
                    # Troca o código por um token de acesso
                    token_info = auth_manager.get_access_token(code)
                    if token_info:
                        cache_handler.save_token_to_cache(token_info)
                        st.success("✅ Login realizado com sucesso!")
                        # Limpa a URL para ficar bonita
                        st.experimental_set_query_params()
                        # Pequena pausa e recarrega
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Não foi possível obter o token de acesso.")
                except Exception as e:
                    error_msg = str(e)
                    st.error(f"Erro ao processar o login: {error_msg}")
                    logger.error(f"Erro OAuth: {error_msg}")
                    
                    # Informações de debug úteis
                    if "invalid_grant" in error_msg:
                        st.info("""
                        **Possíveis causas:**
                        1. O código de autorização expirou (válido por apenas 30 segundos)
                        2. O Redirect URI não está configurado corretamente
                        3. O app não está em modo de desenvolvimento com seu email adicionado
                        """)
                    
                    # Mostrar informações para debug
                    with st.expander("🔧 Informações para Debug"):
                        st.write(f"**Client ID:** {client_id[:10]}...")
                        st.write(f"**Redirect URI:** {redirect_uri}")
                        st.write(f"**Escopo:** {scope}")
                        st.write("**URL atual:**", st.experimental_get_query_params())

            # 2. Verifica se já temos um token válido na sessão
            token_info = cache_handler.get_cached_token()
            
            if token_info:
                # Verifica se o token está expirado
                if auth_manager.is_token_expired(token_info):
                    try:
                        # Tenta renovar o token
                        token_info = auth_manager.refresh_access_token(token_info.get('refresh_token'))
                        cache_handler.save_token_to_cache(token_info)
                    except Exception as e:
                        logger.warning(f"Não foi possível renovar o token: {e}")
                        cache_handler.clear_token()
                        token_info = None
            
            if token_info and not auth_manager.is_token_expired(token_info):
                # Token válido encontrado - criar cliente Spotify
                self.sp = spotipy.Spotify(auth_manager=auth_manager)
                self.is_authenticated = True
                
                # Obter informações do usuário
                try:
                    user = self.sp.current_user()
                    st.session_state.user_name = user.get('display_name', 'Usuário')
                    st.session_state.user_id = user.get('id', '')
                    
                    # Salvar informações do usuário
                    if 'images' in user and user['images']:
                        st.session_state.user_image = user['images'][0]['url']
                    else:
                        st.session_state.user_image = None
                        
                    logger.info(f"Conectado ao Spotify como: {user.get('display_name')}")
                    
                except Exception as e:
                    logger.error(f"Erro ao obter dados do usuário: {e}")
                    st.session_state.user_name = "Usuário"
                    st.session_state.user_image = None
                    
            else:
                # 3. Se não tem token, mostra o botão de login
                self.is_authenticated = False
                self.sp = None
                
                # Gera a URL de autorização
                try:
                    auth_url = auth_manager.get_authorize_url()
                    
                    # Interface de Login
                    st.markdown("""
                    <style>
                    .login-container {
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        min-height: 70vh;
                        text-align: center;
                        padding: 2rem;
                    }
                    .login-button {
                        background-color: #1DB954;
                        color: white;
                        padding: 15px 30px;
                        border-radius: 30px;
                        text-decoration: none;
                        font-weight: bold;
                        font-size: 18px;
                        display: inline-block;
                        margin: 20px 0;
                        border: none;
                        transition: all 0.3s ease;
                    }
                    .login-button:hover {
                        background-color: #1ED760;
                        transform: scale(1.05);
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    
                    st.markdown('<div class="login-container">', unsafe_allow_html=True)
                    st.markdown('<h1 style="color: #1DB954; font-size: 2.5rem;">🎵 Spotify Insights AI</h1>', unsafe_allow_html=True)
                    st.markdown('<p style="color: #B3B3B3; font-size: 1.2rem; margin-bottom: 30px;">Analise seus hábitos musicais com IA</p>', unsafe_allow_html=True)
                    
                    # Botão de login
                    st.markdown(f'''
                    <a href="{auth_url}" target="_self">
                        <button class="login-button">
                            🟢 Conectar com Spotify
                        </button>
                    </a>
                    ''', unsafe_allow_html=True)
                    
                    st.markdown('<p style="color: #888; margin-top: 20px;">Você será redirecionado para a página segura de login do Spotify.</p>', unsafe_allow_html=True)
                    
                    # Informações para desenvolvedores
                    with st.expander("⚙️ Informações para Desenvolvedores"):
                        st.info(f"""
                        **Configurações necessárias no Spotify Developer Dashboard:**
                        
                        1. **Redirect URIs:** Adicione exatamente esta URL:
                           `{redirect_uri}`
                        
                        2. **Modo de Desenvolvimento:** 
                           - Seu app está em "Development Mode"
                           - Adicione seu email em "Users and Access"
                        
                        3. **Para produção:** Solicite "Quota Extension" para sair do modo desenvolvimento
                        
                        **URLs comuns:**
                        - Local: `http://localhost:8501`
                        - Streamlit Cloud: `https://seu-app.streamlit.app`
                        """)
                        
                        if st.button("📋 Copiar Redirect URI"):
                            st.code(redirect_uri, language="text")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Para a execução aqui
                    st.stop()
                    
                except Exception as e:
                    st.error(f"Erro ao gerar URL de autorização: {str(e)}")
                    st.stop()
        
        except Exception as e:
            logger.error(f"Erro crítico ao configurar Spotify: {e}")
            st.error(f"Erro de configuração: {str(e)}")
            st.stop()
    
    # ... (mantenha todos os outros métodos como estão) ...

    def logout(self):
        """Realiza logout do usuário"""
        cache_handler = StreamlitSessionCacheHandler()
        cache_handler.clear_token()
        
        # Limpar outras informações da sessão
        keys_to_clear = ['user_name', 'user_image', 'user_id']
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        
        # Limpar o assistente
        if 'assistant' in st.session_state:
            del st.session_state.assistant
        
        st.success("✅ Logout realizado com sucesso!")
        time.sleep(1)
        st.rerun()

# ========== FUNÇÕES DE VISUALIZAÇÃO (MANTIDAS) ==========

def create_audio_features_radar(features_dict: Dict[str, float]):
    """Cria um gráfico de radar com as características de áudio"""
    
    categories = ['Dançabilidade', 'Energia', 'Humor (Valence)', 'Acústica', 'Instrumentalidade']
    r_values = [
        features_dict.get('danceability', 0),
        features_dict.get('energy', 0),
        features_dict.get('valence', 0),
        features_dict.get('acousticness', 0),
        features_dict.get('instrumentalness', 0)
    ]
    
    # Fechar o ciclo do gráfico
    r_values.append(r_values[0])
    categories.append(categories[0])

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=r_values,
        theta=categories,
        fill='toself',
        name='Sua Vibe Musical',
        line_color='#1DB954'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                color='white'
            ),
            bgcolor='rgba(0,0,0,0)'
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        title="Assinatura Sonora (Audio Features)",
        showlegend=False
    )

    return fig

def create_era_timeline(decade_distribution: Dict[int, int]):
    """Cria uma linha do tempo das décadas musicais"""
    if not decade_distribution:
        return None
    
    # Ordenar décadas
    sorted_decades = sorted(decade_distribution.items())
    decades = [str(decade) for decade, _ in sorted_decades]
    counts = [count for _, count in sorted_decades]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=decades,
        y=counts,
        marker_color='#1DB954',
        text=counts,
        textposition='auto',
    ))
    
    fig.update_layout(
        title="Distribuição por Década",
        xaxis_title="Década",
        yaxis_title="Número de Músicas",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='white'
    )
    
    return fig

def create_feature_breakdown(features_dict: Dict[str, float]):
    """Cria um gráfico de barras com todas as features"""
    
    feature_labels = {
        'danceability': 'Dançabilidade',
        'energy': 'Energia',
        'valence': 'Humor (Positividade)',
        'acousticness': 'Acústica',
        'instrumentalness': 'Instrumentalidade',
        'speechiness': 'Fala (Speechiness)',
        'liveness': 'Ao Vivo',
        'tempo': 'Tempo (BPM)',
        'loudness': 'Volume'
    }
    
    labels = []
    values = []
    descriptions = []
    
    for key, label in feature_labels.items():
        if key in features_dict:
            value = features_dict[key]
            labels.append(label)
            values.append(value)
            
            if key == 'valence':
                desc = 'Triste' if value < 0.3 else 'Neutro' if value < 0.7 else 'Feliz'
            elif key == 'energy':
                desc = 'Calma' if value < 0.3 else 'Moderada' if value < 0.7 else 'Intensa'
            elif key == 'danceability':
                desc = 'Baixa' if value < 0.3 else 'Moderada' if value < 0.7 else 'Alta'
            elif key == 'acousticness':
                desc = 'Eletrônica' if value < 0.3 else 'Mista' if value < 0.7 else 'Acústica'
            elif key == 'tempo':
                desc = f'{value:.0f} BPM'
            elif key == 'loudness':
                desc = f'{value:.1f} dB'
            else:
                desc = f'{value:.2%}'
            
            descriptions.append(desc)
    
    fig = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            text=descriptions,
            textposition='auto',
            marker_color=['#1DB954' if v > 0.5 else '#FF6B6B' for v in values],
            hovertext=[f'{label}: {desc}' for label, desc in zip(labels, descriptions)],
            hoverinfo='text'
        )
    ])
    
    fig.update_layout(
        title="Análise Detalhada de Audio Features",
        xaxis_title="Características",
        yaxis_title="Valor (0-1)",
        yaxis=dict(range=[0, 1]),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        xaxis_tickangle=-45
    )
    
    return fig

# ========== FUNÇÕES DE EXIBIÇÃO BÁSICAS ==========

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

# ========== FUNÇÕES PARA ANÁLISE PROFUNDA ==========

def display_deep_analysis(assistant):
    """Exibe análise profunda do perfil musical"""
    if not assistant.is_authenticated:
        st.warning("⚠️ Você precisa estar autenticado para acessar esta análise.")
        return
    
    st.markdown('<h3 class="sub-header">🔍 Análise Profunda do Perfil Musical</h3>', unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎵 Audio Features", 
        "📅 Era Musical", 
        "🎶 Gêneros Detalhados", 
        "🧠 Análise Completa"
    ])
    
    with tab1:
        display_audio_features_analysis(assistant)
    
    with tab2:
        display_era_analysis(assistant)
    
    with tab3:
        display_genre_analysis(assistant)
    
    with tab4:
        display_complete_analysis(assistant)

def display_audio_features_analysis(assistant):
    """Análise de características de áudio"""
    st.markdown("### 🎵 Análise de Audio Features")
    st.markdown("Descubra o *humor* e *estrutura técnica* das suas músicas favoritas.")
    
    time_range = st.selectbox(
        "Período para análise:",
        ["short_term (4 semanas)", "medium_term (6 meses)", "long_term (varios anos)"],
        index=1,
        key="audio_features_range"
    )
    
    time_map = {
        "short_term (4 semanas)": "short_term",
        "medium_term (6 meses)": "medium_term",
        "long_term (varios anos)": "long_term"
    }
    
    limit = st.slider("Número de músicas para análise:", 10, 100, 30, key="audio_features_limit")
    
    if st.button("🔍 Analisar Características de Áudio", use_container_width=True):
        with st.spinner("Analisando suas músicas..."):
            tracks_result = assistant.get_top_tracks(limit=limit, time_range=time_map[time_range])
            
            if tracks_result["status"] == "success":
                tracks_data = tracks_result["data"]
                track_ids = [track['id'] for track in tracks_data if track.get('id')]
                
                features_result = assistant.get_audio_features_stats(track_ids)
                
                if features_result["status"] == "success":
                    features = features_result["averages"]
                    key_analysis = features_result.get("key_analysis", {})
                    
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        radar_fig = create_audio_features_radar(features)
                        st.plotly_chart(radar_fig, use_container_width=True)
                    
                    with col2:
                        st.markdown("#### 📊 Métricas Principais")
                        
                        def get_mood_emoji(valence, energy):
                            if valence > 0.7 and energy > 0.7:
                                return "😄🎉"
                            elif valence > 0.7 and energy <= 0.7:
                                return "😊✨"
                            elif valence <= 0.7 and energy > 0.7:
                                return "😤⚡"
                            else:
                                return "😌🎧"
                        
                        mood_emoji = get_mood_emoji(features.get('valence', 0), features.get('energy', 0))
                        
                        st.metric("Estado de Espírito", mood_emoji, 
                                 f"{features.get('valence', 0):.0%}")
                        st.metric("Nível de Energia", 
                                 f"{features.get('energy', 0):.0%}",
                                 "⚡" if features.get('energy', 0) > 0.7 else "🔋")
                        st.metric("Dançabilidade", 
                                 f"{features.get('danceability', 0):.0%}",
                                 "💃🕺" if features.get('danceability', 0) > 0.7 else "🎵")
                        
                        if key_analysis:
                            st.metric("Tom Predominante", 
                                     f"{key_analysis.get('most_common_key', 'N/A')}",
                                     key_analysis.get('most_common_mode', ''))
                    
                    st.markdown("---")
                    feature_fig = create_feature_breakdown(features)
                    st.plotly_chart(feature_fig, use_container_width=True)
                    
                    if st.button("🤖 Gerar Análise Detalhada", key="audio_features_analysis"):
                        with st.spinner("Criando análise personalizada..."):
                            analysis_data = {
                                "audio_features": features,
                                "key_analysis": key_analysis,
                                "sample_tracks": tracks_data[:3]
                            }
                            
                            prompt = f"""
                            Analise o perfil musical deste usuário com base nestes dados técnicos:

                            1. Audio Features (Médias de 0 a 1):
                               - Felicidade/Positividade (Valence): {features.get('valence', 0):.2f}
                               - Energia: {features.get('energy', 0):.2f}
                               - Dançabilidade: {features.get('danceability', 0):.2f}
                               - Acústica: {features.get('acousticness', 0):.2f}
                               - Instrumentalidade: {features.get('instrumentalness', 0):.2f}

                            2. Tom Musical:
                               - Chave mais comum: {key_analysis.get('most_common_key', 'N/A')}
                               - Modo: {key_analysis.get('most_common_mode', 'N/A')}

                            Me forneça uma análise detalhada que inclua:
                            - Qual é o "Estado de Espírito" principal do usuário baseado na Valence e Energy?
                            - Baseado na Danceability e Energy, que tipo de atividade essas músicas combinam?
                            - O que a combinação de Acousticness e Instrumentalness revela sobre o gosto do usuário?
                            - Como o tom musical predominante se relaciona com as características emocionais?

                            Seja criativo, pessoal e use emojis para tornar a análise mais envolvente!
                            """
                            
                            analysis = assistant.analyze_with_gemini(prompt, analysis_data)
                            st.markdown(f'<div class="insight-box">{analysis}</div>', unsafe_allow_html=True)
                else:
                    st.error(f"Erro ao obter audio features: {features_result.get('message')}")
            else:
                st.error(f"Erro ao carregar músicas: {tracks_result.get('message')}")

def display_era_analysis(assistant):
    """Análise de eras musicais"""
    st.markdown("### 📅 Viagem no Tempo Musical")
    st.markdown("Descubra em que década suas músicas favoritas foram lançadas.")
    
    display_limit = st.slider("Número de músicas para análise:", 20, 50, 30, key="era_display_limit")
    internal_limit = 200
    
    if st.button("🕰️ Analisar Minha Linha do Tempo", use_container_width=True, key="analyze_era"):
        with st.spinner("Analisando suas músicas..."):
            saved_result = assistant.get_saved_tracks(limit=internal_limit)
            
            if saved_result["status"] == "success":
                tracks_data = saved_result["data"]
                display_data = tracks_data[:display_limit]
                era_result = assistant.get_era_analysis(tracks_data)
                
                if era_result["status"] == "success":
                    era_data = era_result["era_analysis"]
                    
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        timeline_fig = create_era_timeline(era_data.get('decade_distribution', {}))
                        if timeline_fig:
                            st.plotly_chart(timeline_fig, use_container_width=True)
                    
                    with col2:
                        st.markdown('<div class="card">', unsafe_allow_html=True)
                        st.markdown("#### 📈 Estatísticas")
                        st.metric("Músicas Analisadas", era_data.get('total_tracks_analyzed', 0))
                        st.metric("Ano Mais Antigo", era_data.get('oldest_year', 'N/A'))
                        st.metric("Ano Mais Recente", era_data.get('newest_year', 'N/A'))
                        st.metric("Média de Ano", f"{era_data.get('average_year', 0):.0f}")
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    st.markdown("---")
                    st.markdown("#### 📊 Distribuição por Década")
                    
                    if era_data.get('decade_percentages'):
                        decade_df = pd.DataFrame(
                            list(era_data['decade_percentages'].items()),
                            columns=['Década', 'Percentual']
                        )
                        decade_df = decade_df.sort_values('Década')
                        
                        fig = px.pie(decade_df, values='Percentual', names='Década',
                                    title="Percentual por Década",
                                    color_discrete_sequence=px.colors.sequential.Viridis)
                        
                        fig.update_layout(
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)',
                            font_color='white'
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    
                    if st.button("🤖 Gerar Análise Temporal", key="era_analysis_ai"):
                        with st.spinner("Criando análise temporal..."):
                            analysis_data = {
                                "era_analysis": era_data,
                                "total_tracks": len(tracks_data)
                            }
                            
                            prompt = f"""
                            Analise a distribuição temporal das músicas deste usuário:

                            Décadas Analisadas: {era_data.get('decade_percentages', {})}
                            Ano mais antigo: {era_data.get('oldest_year', 'N/A')}
                            Ano mais recente: {era_data.get('newest_year', 'N/A')}
                            Média de ano: {era_data.get('average_year', 'N/A')}
                            Total de músicas analisadas: {era_data.get('total_tracks_analyzed', 0)}

                            Forneça uma análise que inclua:
                            1. Qual década predomina e o que isso revela sobre o usuário?
                            2. Como a faixa etária das músicas se compara com a idade do usuário (se possível inferir)?
                            3. O usuário é mais nostálgico ou atualizado?
                            4. Sugestões de músicas de décadas sub-representadas

                            Seja específico e ofereça insights interessantes!
                            """
                            
                            analysis = assistant.analyze_with_gemini(prompt, analysis_data)
                            st.markdown(f'<div class="insight-box">{analysis}</div>', unsafe_allow_html=True)
                else:
                    st.error(f"Erro na análise de era: {era_result.get('message')}")
            else:
                st.error(f"Erro ao obter músicas salvas: {saved_result.get('message')}")

def display_genre_analysis(assistant):
    """Análise detalhada de gêneros"""
    st.markdown("### 🎶 Análise de Gêneros Detalhada")
    st.markdown("Explore sua diversidade musical através dos gêneros dos seus artistas favoritos.")
    
    limit = st.slider("Número de artistas para análise:", 20, 100, 50, key="genre_limit")
    
    if st.button("🎵 Analisar Meus Gêneros", use_container_width=True):
        with st.spinner("Analisando seus gêneros musicais..."):
            genre_result = assistant.get_genre_analysis(limit=limit)
            
            if genre_result["status"] == "success":
                genre_data = genre_result["genre_analysis"]
                top_genres = genre_data.get('top_genres', {})
                
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    if top_genres:
                        genres_df = pd.DataFrame(
                            list(top_genres.items()), 
                            columns=['Gênero', 'Frequência']
                        ).sort_values('Frequência', ascending=False).head(10)
                        
                        fig = px.bar(
                            genres_df, 
                            x='Gênero', 
                            y='Frequência',
                            title="Top 10 Gêneros",
                            color='Frequência',
                            color_continuous_scale='Viridis'
                        )
                        
                        fig.update_layout(
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)',
                            font_color='white',
                            xaxis_tickangle=-45
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.markdown("#### 📊 Diversidade")
                    st.metric("Gêneros Únicos", genre_data.get('unique_genres', 0))
                    st.metric("Artistas Analisados", genre_data.get('total_artists', 0))
                    st.metric("Diversidade", f"{genre_data.get('genre_diversity', 0)}%")
                    
                    diversity_score = genre_data.get('genre_diversity', 0)
                    if diversity_score > 150:
                        diversity_emoji = "🎭🌍"
                        diversity_text = "Ecletismo Total"
                    elif diversity_score > 100:
                        diversity_emoji = "🎸🎹"
                        diversity_text = "Muito Diverso"
                    elif diversity_score > 50:
                        diversity_emoji = "🎵🎶"
                        diversity_text = "Bem Balanceado"
                    else:
                        diversity_emoji = "🎧"
                        diversity_text = "Focado"
                    
                    st.metric("Perfil de Gosto", diversity_emoji, diversity_text)
                
                st.markdown("---")
                st.markdown("#### 🎤 Artistas e Seus Gêneros")
                
                artist_genres = genre_data.get('genre_by_artist', {})
                if artist_genres:
                    artist_data = []
                    for artist, genres in list(artist_genres.items())[:15]:
                        artist_data.append({
                            "Artista": artist,
                            "Gêneros": ", ".join(genres[:3]),
                            "Total Gêneros": len(genres)
                        })
                    
                    df = pd.DataFrame(artist_data)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                
                if st.button("🤖 Gerar Análise de Gêneros", key="genre_analysis"):
                    with st.spinner("Criando análise de gêneros..."):
                        analysis_data = {
                            "genre_analysis": genre_data,
                            "top_genres_sample": dict(list(top_genres.items())[:10])
                        }
                        
                        prompt = f"""
                        Analise o perfil de gêneros musicais deste usuário:

                        Top Gêneros: {json.dumps(analysis_data['top_genres_sample'], ensure_ascii=False)}

                        Estatísticas:
                        - Gêneros únicos: {genre_data.get('unique_genres', 0)}
                        - Artistas analisados: {genre_data.get('total_artists', 0)}
                        - Índice de diversidade: {genre_data.get('genre_diversity', 0)}%

                        Forneça uma análise que inclua:
                        1. Qual é o gênero predominante e o que isso revela sobre o usuário?
                        2. A diversidade de gêneros: O usuário é eclético ou nichado?
                        3. Quais subgêneros ou artistas similares você recomendaria?
                        4. Como esses gêneros se relacionam entre si?

                        Seja específico e ofereça recomendações personalizadas!
                        """
                        
                        analysis = assistant.analyze_with_gemini(prompt, analysis_data)
                        st.markdown(f'<div class="insight-box">{analysis}</div>', unsafe_allow_html=True)
            else:
                st.error(f"Erro na análise de gêneros: {genre_result.get('message')}")

def display_complete_analysis(assistant):
    """Análise completa integrando todos os dados"""
    if not assistant.is_authenticated:
        st.warning("⚠️ Você precisa estar autenticado para acessar esta análise.")
        return
    
    st.markdown("### 🧠 Análise de Perfil Completa")
    st.markdown("Uma análise integrada de todos os aspectos do seu perfil musical.")
    
    st.info("""
    Esta análise combina:
    - 🎵 **Audio Features**: Humor, energia e características técnicas
    - 📅 **Era Musical**: Distribuição temporal das suas músicas
    - 🎶 **Gêneros**: Diversidade e preferências
    - 👤 **Comportamento**: Padrões de escuta e preferências
    """)
    
    if st.button("🚀 Gerar Análise de Perfil Completa", use_container_width=True):
        with st.spinner("Coletando e analisando todos os seus dados..."):
            progress_bar = st.progress(0)
            
            progress_bar.progress(10)
            tracks_result = assistant.get_top_tracks(limit=30, time_range="medium_term")
            
            progress_bar.progress(30)
            artists_result = assistant.get_top_artists(limit=30, time_range="medium_term")
            
            progress_bar.progress(50)
            recent_result = assistant.get_recently_played(limit=20)
            
            progress_bar.progress(70)
            if tracks_result["status"] == "success":
                track_ids = [t['id'] for t in tracks_result["data"] if t.get('id')]
                features_result = assistant.get_audio_features_stats(track_ids)
            else:
                features_result = {"status": "error"}
            
            progress_bar.progress(90)
            if tracks_result["status"] == "success":
                era_result = assistant.get_era_analysis(tracks_result["data"])
            else:
                era_result = {"status": "error"}
            
            progress_bar.progress(100)
            
            complete_data = {
                "profile": assistant.get_user_profile().get("data", {}),
                "top_tracks": tracks_result.get("data", [])[:10] if tracks_result["status"] == "success" else [],
                "top_artists": artists_result.get("data", [])[:10] if artists_result["status"] == "success" else [],
                "recent_tracks": recent_result.get("data", [])[:10] if recent_result["status"] == "success" else [],
                "audio_features": features_result.get("averages", {}) if features_result["status"] == "success" else {},
                "era_analysis": era_result.get("era_analysis", {}) if era_result["status"] == "success" else {},
                "timestamp": datetime.now().isoformat()
            }
            
            st.markdown("---")
            st.markdown("### 📋 Resumo dos Dados Coletados")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Músicas Analisadas", len(complete_data["top_tracks"]))
            
            with col2:
                st.metric("Artistas Analisados", len(complete_data["top_artists"]))
            
            with col3:
                if complete_data["audio_features"]:
                    energy = complete_data["audio_features"].get('energy', 0)
                    st.metric("Energia Média", f"{energy:.0%}")
            
            with col4:
                if complete_data["era_analysis"]:
                    decade_items = complete_data["era_analysis"].get('decade_distribution', {}).items()
                    if decade_items:
                        decade = max(decade_items, key=lambda x: x[1], default=(None, 0))[0]
                        st.metric("Década Dominante", f"{decade}s" if decade else "N/A")
            
            prompt = f"""
            Você é um psicólogo musical especializado em análise de perfis. 
            Analise profundamente estes dados do Spotify:

            PERFIL DO USUÁRIO:
            Nome: {complete_data["profile"].get("display_name", "Usuário")}
            País: {complete_data["profile"].get("country", "N/A")}
            Tipo de Conta: {complete_data["profile"].get("product", "N/A")}

            PREFERÊNCIAS MUSICAIS:

            1. TOP MÚSICAS (Humor Técnico):
               - Felicidade Musical (Valence): {complete_data["audio_features"].get('valence', 0.5):.2f}/1.0
               - Nível de Energia: {complete_data["audio_features"].get('energy', 0.5):.2f}/1.0
               - Dançabilidade: {complete_data["audio_features"].get('danceability', 0.5):.2f}/1.0
               - Acústica: {complete_data["audio_features"].get('acousticness', 0.5):.2f}/1.0

            2. ERA MUSICAL:
               - Faixa de anos: {complete_data["era_analysis"].get('year_range', 'N/A')}
               - Década predominante: {max(complete_data["era_analysis"].get('decade_distribution', {}).items(), key=lambda x: x[1], default=('N/A', 0))[0]}

            3. COMPORTAMENTO RECENTE:
               - Músicas ouvidas recentemente: {len(complete_data["recent_tracks"])}

            Forneça uma análise psicológica/musical completa que inclua:

            🧠 ANÁLISE PSICOLÓGICA:
            - Qual é o estado emocional predominante do usuário?
            - Como a música funciona como coping mechanism?
            - Padrões de humor ao longo do tempo (baseado na era)?

            🎵 ANÁLISE MUSICAL:
            - Assinatura sonora única do usuário
            - Como as características técnicas se relacionam com os gêneros?
            - Evolução do gosto musical ao longo do tempo

            💡 RECOMENDAÇÕES PERSONALIZADAS:
            - 3 artistas que o usuário DEVERIA conhecer
            - 1 gênero musical para explorar
            - 1 década musical para redescobrir

            Seja extremamente detalhado, pessoal e use metáforas musicais criativas.
            """
            
            analysis = assistant.analyze_with_gemini(prompt, complete_data)
            
            st.markdown("---")
            st.markdown("### 🧠 Análise Psicológica Musical")
            
            sections = analysis.split('\n\n')
            for section in sections:
                if section.strip():
                    if any(marker in section.lower() for marker in ['psicológica', 'emocional', 'estado']):
                        st.markdown(f'<div class="card">{section}</div>', unsafe_allow_html=True)
                    elif any(marker in section.lower() for marker in ['musical', 'técnica', 'assinatura']):
                        st.markdown(f'<div class="insight-box">{section}</div>', unsafe_allow_html=True)
                    elif any(marker in section.lower() for marker in ['recomenda', 'sugest', 'conhecer']):
                        st.markdown(f'<div style="background-color: #2a2a2a; padding: 1rem; border-radius: 10px; margin: 1rem 0;">{section}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(section)
            
            if st.button("💾 Salvar Esta Análise", key="save_analysis"):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"analise_musical_{timestamp}.txt"
                
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(f"ANÁLISE MUSICAL COMPLETA\n")
                    f.write(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
                    f.write(f"Usuário: {complete_data['profile'].get('display_name', 'N/A')}\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(analysis)
                
                st.success(f"✅ Análise salva como '{filename}'")
                
                with open(filename, "r", encoding="utf-8") as f:
                    file_content = f.read()
                
                b64 = base64.b64encode(file_content.encode()).decode()
                href = f'<a href="data:file/txt;base64,{b64}" download="{filename}">📥 Clique para baixar a análise</a>'
                st.markdown(href, unsafe_allow_html=True)

# ========== FUNÇÕES PRINCIPAIS ==========
def debug_auth_info():
    """Função para debug da autenticação"""
    with st.expander("🔍 Debug - Informações de Autenticação"):
        st.write("**Keys no session_state:**", list(st.session_state.keys()))
        
        if 'spotify_token' in st.session_state:
            token = st.session_state.spotify_token
            if token:
                st.write("✅ Token presente")
                import time
                expiry = token.get('expires_at', 0)
                current = time.time()
                if expiry > current:
                    mins_left = int((expiry - current) / 60)
                    st.write(f"⏳ Expira em: {mins_left} minutos")
                else:
                    st.write("❌ Token expirado")
            else:
                st.write("❌ Token vazio")
        else:
            st.write("❌ Token não encontrado")
        
        st.write("**Query params:**", st.experimental_get_query_params())
        
        # Testar se as credenciais estão carregadas
        try:
            client_id = st.secrets.get("SPOTIFY_CLIENT_ID", os.getenv("SPOTIFY_CLIENT_ID"))
            if client_id:
                st.write(f"✅ Client ID carregado: {client_id[:10]}...")
            else:
                st.write("❌ Client ID NÃO carregado")
        except:
            st.write("❌ Erro ao acessar credenciais")

def main():
    """Função principal da aplicação Streamlit"""
    
    # Título principal
    st.markdown('<h1 class="main-header">🎵 Spotify Insights AI</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #B3B3B3;">Analise seus hábitos musicais com IA</p>', unsafe_allow_html=True)
    if st.sidebar.button("🔧 Debug Info", key="debug_button"):
        debug_auth_info()

    # Inicializar sessão
    if 'assistant' not in st.session_state:
        try:
            with st.spinner("🔗 Conectando ao Spotify e Gemini..."):
                st.session_state.assistant = SpotifyGeminiAssistant()
                # O construtor já para a execução se não estiver autenticado
                # Se chegou aqui, é porque está autenticado
        except Exception as e:
            st.error(f"❌ Erro ao inicializar: {str(e)}")
            return
    
    assistant = st.session_state.assistant
    
    # Verificar se o usuário está autenticado
    if not hasattr(assistant, 'is_authenticated') or not assistant.is_authenticated:
        # Se não estiver autenticado, o construtor já mostrou a tela de login
        return
    
    # Sidebar com menu (só aparece se autenticado)
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
            options=["Dashboard", "Top Músicas", "Top Artistas", "Histórico", "Playlists", "Análise Profunda", "Chat AI"],
            icons=["house", "music-note", "person", "clock", "list", "bar-chart", "robot"],
            default_index=0,
            styles= {
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
        
        st.markdown("---")
        
        # Botão de logout
        if st.button("🚪 Sair da Conta", use_container_width=True):
            assistant.logout()
    
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
    elif menu == "Análise Profunda":
        display_deep_analysis(assistant)
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
            data = {
                "top_tracks": assistant.get_top_tracks(limit=10, time_range=time_range),
                "top_artists": assistant.get_top_artists(limit=10, time_range=time_range),
                "recent_tracks": assistant.get_recently_played(limit=10)
            }
            
            prompt = "Analise meus dados do Spotify e forneça insights interessantes sobre meus hábitos musicais."
            insights = assistant.analyze_with_gemini(prompt, data)
            
            st.markdown(f'<div class="insight-box">{insights}</div>', unsafe_allow_html=True)

def display_top_tracks(assistant, time_range):
    """Exibe top músicas"""
    st.markdown(f'<h3 class="sub-header">🎵 Suas Músicas Mais Ouvidas ({time_range})</h3>', unsafe_allow_html=True)
    
    limit = st.slider("Número de músicas:", 5, 50, 20, key="top_tracks_limit")
    
    with st.spinner("Carregando suas músicas..."):
        tracks_result = assistant.get_top_tracks(limit=limit, time_range=time_range)
    
    if tracks_result["status"] == "success":
        tracks_data = tracks_result["data"]
        
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            search = st.text_input("🔍 Buscar música ou artista:", "", key="track_search")
        
        with col_filter2:
            min_popularity = st.slider("Popularidade mínima:", 0, 100, 50, key="track_popularity")
        
        filtered_tracks = [
            t for t in tracks_data 
            if t['popularity'] >= min_popularity and
            (search.lower() in t['name'].lower() or search.lower() in t['artist'].lower())
        ]
        
        if filtered_tracks:
            avg_popularity = sum(t['popularity'] for t in filtered_tracks) / len(filtered_tracks)
            total_duration = sum(t['duration_ms'] for t in filtered_tracks) / 60000
            
            col_stats1, col_stats2, col_stats3 = st.columns(3)
            with col_stats1:
                st.metric("Total de Músicas", len(filtered_tracks))
            with col_stats2:
                st.metric("Popularidade Média", f"{avg_popularity:.1f}%")
            with col_stats3:
                st.metric("Duração Total", f"{total_duration:.0f} min")
            
            st.markdown("---")
            for i, track in enumerate(filtered_tracks, 1):
                display_track(track)
            
            if st.button("📊 Analisar Essas Músicas com IA", key="analyze_tracks"):
                with st.spinner("Gerando análise..."):
                    analysis_data = {
                        "tracks": filtered_tracks,
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
    
    limit = st.slider("Número de artistas:", 5, 50, 20, key="top_artists_limit")
    
    with st.spinner("Carregando seus artistas..."):
        artists = assistant.get_top_artists(limit=limit, time_range=time_range)
    
    if artists["status"] == "success":
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            search = st.text_input("🔍 Buscar artista:", "", key="artist_search")
        
        with col_filter2:
            min_popularity = st.slider("Popularidade mínima:", 0, 100, 50, key="artist_popularity")
        
        filtered_artists = [
            a for a in artists["data"] 
            if a['popularity'] >= min_popularity and
            search.lower() in a['name'].lower()
        ]
        
        if filtered_artists:
            avg_popularity = sum(a['popularity'] for a in filtered_artists) / len(filtered_artists)
            total_followers = sum(a['followers'] for a in filtered_artists)
            
            col_stats1, col_stats2 = st.columns(2)
            with col_stats1:
                st.metric("Total de Artistas", len(filtered_artists))
            with col_stats2:
                st.metric("Seguidores Totais", f"{total_followers:,}")
            
            all_genres = []
            for artist in filtered_artists:
                all_genres.extend(artist['genres'])
            
            genre_counts = Counter(all_genres)
            
            if genre_counts:
                top_genres = genre_counts.most_common(5)
                st.markdown("#### 🎶 Gêneros Mais Comuns")
                for genre, count in top_genres:
                    st.progress(count / len(filtered_artists))
                    st.caption(f"{genre}: {count} artistas")
            
            st.markdown("---")
            st.markdown("#### 🏆 Seus Artistas")
            for artist in filtered_artists:
                display_artist(artist)
            
            if st.button("🤖 Analisar Meus Artistas com IA", key="analyze_artists"):
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
    
    limit = st.slider("Número de reproduções recentes:", 10, 100, 30, key="recent_limit")
    
    with st.spinner("Carregando seu histórico..."):
        recent = assistant.get_recently_played(limit=limit)
    
    if recent["status"] == "success":
        if recent["data"]:
            st.markdown("#### 📈 Atividade por Hora")
            
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
            
            st.markdown("---")
            st.markdown(f"#### 🎧 Últimas {len(recent['data'])} Reproduções")
            
            for track in recent["data"]:
                display_track(track, show_album=False, show_popularity=False)
            
            if st.button("🧠 Obter Insights do Histórico", key="analyze_history"):
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
            total_tracks = sum(p['tracks'] for p in playlists["data"])
            avg_tracks = total_tracks / len(playlists["data"])
            
            col_stats1, col_stats2 = st.columns(2)
            with col_stats1:
                st.metric("Total de Playlists", len(playlists["data"]))
            with col_stats2:
                st.metric("Média de Músicas", f"{avg_tracks:.0f}")
            
            st.markdown("---")
            cols = st.columns(4)
            
            for idx, playlist in enumerate(playlists["data"]):
                with cols[idx % 4]:
                    with st.container():
                        if playlist['image_url']:
                            try:
                                response = requests.get(playlist['image_url'])
                                img = Image.open(BytesIO(response.content))
                                st.image(img, use_container_width=True)
                            except:
                                st.image("📋", use_container_width=True)
                        else:
                            st.image("📋", use_container_width=True)
                        
                        st.write(f"**{playlist['name'][:20]}...**" if len(playlist['name']) > 20 else f"**{playlist['name']}**")
                        st.caption(f"{playlist['tracks']} músicas")
                        
                        if playlist['description']:
                            with st.expander("Descrição"):
                                st.write(playlist['description'])
            
            if st.button("🎯 Analisar Minhas Playlists", key="analyze_playlists"):
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
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    with st.expander("💡 **Sugestões Rápidas**", expanded=True):
        cols = st.columns(2)
        suggestions = [
            ("🎵 Músicas mais ouvidas", "Quais são minhas músicas mais ouvidas?"),
            ("👨‍🎤 Artistas favoritos", "Quem são meus artistas favoritos?"),
            ("🎯 Recomendações", "Me dê recomendações musicais baseadas no meu gosto"),
            ("📊 Análise de hábitos", "Analise meus hábitos de escuta e me dê insights"),
            ("🕐 Histórico recente", "O que eu tenho ouvido recentemente?"),
            ("🎶 Gêneros musicais", "Quais são meus gêneros musicais preferidos?")
        ]
        
        for i, (icon_text, question) in enumerate(suggestions):
            col = cols[i % 2]
            if col.button(f"{icon_text}", key=f"suggest_{i}", use_container_width=True):
                process_question(assistant, question)
    
    st.markdown("---")
    
    if prompt := st.chat_input("Digite sua pergunta aqui..."):
        process_question(assistant, prompt)

def process_question(assistant, question):
    """Processa uma pergunta e atualiza o chat"""
    st.session_state.messages.append({"role": "user", "content": question})
    
    with st.chat_message("user"):
        st.markdown(question)
    
    with st.chat_message("assistant"):
        with st.spinner("Analisando seus dados..."):
            context_data = collect_context_data(assistant, question)
            response = assistant.analyze_with_gemini(question, context_data)
            st.markdown(response)
    
    st.session_state.messages.append({"role": "assistant", "content": response})

def collect_context_data(assistant, question):
    """Coleta dados contextuais baseados na pergunta"""
    context_data = {}
    question_lower = question.lower()
    
    keyword_mappings = [
        (["música", "track", "canção", "song"], 
         lambda: assistant.get_top_tracks(limit=20, time_range="medium_term")),
        (["artista", "banda", "artist", "cantor"], 
         lambda: assistant.get_top_artists(limit=20, time_range="medium_term")),
        (["recente", "histórico", "history", "recent"], 
         lambda: assistant.get_recently_played(limit=20)),
        (["tocando", "agora", "current", "playing"], 
         lambda: assistant.get_currently_playing()),
        (["playlist", "lista"], 
         lambda: assistant.get_playlists(limit=10))
    ]
    
    for keywords, func in keyword_mappings:
        if any(keyword in question_lower for keyword in keywords):
            result = func()
            if result["status"] == "success":
                key_name = func.__name__ if hasattr(func, '__name__') else keywords[0]
                context_data[key_name] = result["data"]
    
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
    
    return context_data
if __name__ == "__main__":
    main()