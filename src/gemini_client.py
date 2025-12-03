"""Cliente para interação com a API Gemini"""
import os
import logging
from typing import Dict, Any

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import streamlit as st

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        self._setup_client()
        
    def _setup_client(self):
        """Configura o cliente Gemini"""
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.7,
                "top_p": 0.95,
                "max_output_tokens": 2048,
            },
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
    
    def analyze_data(self, query: str, context: Dict[str, Any]) -> str:
        """Analisa dados com Gemini"""
        try:
            prompt = f"""
            Como especialista em análise musical, analise estes dados do Spotify:
            
            Pergunta: {query}
            
            Dados: {context}
            
            Forneça uma resposta informativa e útil.
            """
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Erro ao processar com Gemini: {e}")
            return f"Desculpe, ocorreu um erro: {str(e)}"