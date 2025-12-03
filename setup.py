import os
from pathlib import Path

def create_project_structure():
    """Cria a estrutura de pastas do projeto"""
    
    base_path = Path("spotify-insights-ai")
    
    # Diretórios principais
    directories = [
        ".streamlit",
        "assets/images",
        "assets/styles",
        "cache",
        "src",
        "pages",
    ]
    
    # Criar diretórios
    for directory in directories:
        dir_path = base_path / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"Criado: {dir_path}")
    
    # Arquivos principais
    files = {
        ".streamlit/config.toml": """[theme]
primaryColor = "#1DB954"
backgroundColor = "#121212"
secondaryBackgroundColor = "#181818"
textColor = "#FFFFFF"
font = "sans serif"

[server]
port = 8501
address = "0.0.0.0"
enableCORS = true

[browser]
gatherUsageStats = false""",
        
        ".streamlit/secrets.toml": """# Spotify API Credentials
SPOTIFY_CLIENT_ID = ""
SPOTIFY_CLIENT_SECRET = ""
SPOTIFY_REDIRECT_URI = ""

# Gemini API Key
GEMINI_API_KEY = ""

# App Configuration
DEBUG = false
ENVIRONMENT = "development" """,
        
        "requirements.txt": """streamlit>=1.28.0
streamlit-option-menu>=0.3.6
plotly>=5.17.0
pandas>=2.0.0
google-generativeai>=0.3.0
spotipy>=2.23.0
pillow>=10.0.0
requests>=2.31.0
python-dotenv>=1.0.0""",
    }
        
