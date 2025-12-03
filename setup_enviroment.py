import subprocess
import sys
import os
import venv
from pathlib import Path

def setup_environment():
    """Configura o ambiente virtual e instala dependências"""
    
    current_dir = Path(__file__).parent
    
    print("🔧 Configurando ambiente Python...")
    
    # 1. Criar ambiente virtual
    venv_path = current_dir / "venv"
    if not venv_path.exists():
        print("📦 Criando ambiente virtual...")
        venv.create(venv_path, with_pip=True)
        print("✅ Ambiente virtual criado")
    
    # 2. Ativar e instalar dependências
    print("📥 Instalando dependências...")
    
    # Determinar o pip do ambiente virtual
    if sys.platform == "win32":
        pip_path = venv_path / "Scripts" / "pip.exe"
        python_path = venv_path / "Scripts" / "python.exe"
    else:
        pip_path = venv_path / "bin" / "pip"
        python_path = venv_path / "bin" / "python"
    
    # Lista de dependências
    requirements = [
        "streamlit>=1.28.0",
        "streamlit-option-menu>=0.3.6",
        "plotly>=5.17.0",
        "pandas>=2.0.0",
        "google-generativeai>=0.3.0",
        "spotipy>=2.23.0",
        "pillow>=10.0.0",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0"
    ]
    
    # Instalar cada pacote individualmente
    for package in requirements:
        print(f"  Instalando {package}...")
        try:
            subprocess.run([str(pip_path), "install", package], check=True)
            print(f"  ✅ {package.split('>=')[0]}")
        except subprocess.CalledProcessError as e:
            print(f"  ❌ Erro ao instalar {package}: {e}")
    
    # 3. Verificar instalações
    print("\n🔍 Verificando instalações...")
    result = subprocess.run([str(python_path), "-c", """
import sys
packages = ['streamlit', 'spotipy', 'google.generativeai', 'plotly', 'pandas']
for pkg in packages:
    try:
        __import__(pkg.replace('.', '_') if '_' in pkg else pkg)
        print(f'✅ {pkg}')
    except ImportError:
        print(f'❌ {pkg}')
    """], capture_output=True, text=True)
    
    print(result.stdout)
    
    # 4. Configurar VS Code
    print("\n⚙️ Configurando VS Code...")
    vscode_dir = current_dir / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    
    settings_content = {
        "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python" if sys.platform != "win32" else "${workspaceFolder}/venv/Scripts/python.exe",
        "python.terminal.activateEnvironment": True,
        "python.languageServer": "Pylance",
        "python.analysis.typeCheckingMode": "basic"
    }
    
    import json
    with open(vscode_dir / "settings.json", "w") as f:
        json.dump(settings_content, f, indent=4)
    
    print("✅ Configuração do VS Code concluída")
    
    print("\n" + "="*50)
    print("🎉 Configuração completa!")
    print("="*50)
    print("\nPróximos passos:")
    print("1. Reinicie o VS Code")
    print("2. Pressione Ctrl+Shift+P e selecione 'Python: Select Interpreter'")
    print("3. Escolha o interpretador em: venv/")
    print(f"4. Execute: {python_path} -m streamlit run spotify_gemini_streamlit.py")
    print("\nSe os erros persistirem:")
    print("- Feche e reabra o VS Code")
    print("- Verifique se o ambiente virtual está ativo no terminal do VS Code")

if __name__ == "__main__":
    setup_environment()