"""
Configurações e constantes do projeto AgentGraph
"""
import os
from dotenv import load_dotenv
import logging

# Carrega variáveis de ambiente
load_dotenv()

# Configurações de API
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Configurações de arquivos e diretórios
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploaded_data")
DEFAULT_CSV_PATH = os.getenv("DEFAULT_CSV_PATH", "tabela.csv")
SQL_DB_PATH = os.getenv("SQL_DB_PATH", "data.db")
UPLOADED_CSV_PATH = os.path.join(UPLOAD_DIR, "tabela.csv")

# Configurações de modelos LLM
LLAMA_MODELS = {
    "LLaMA 70B": "meta-llama/Llama-3.3-70B-Instruct",
    "LlaMA 8B": "meta-llama/Llama-3.1-8B-Instruct",
    "DeepSeek-R1": "deepseek-ai/DeepSeek-R1-0528",
    "o3-mini": "o3-mini",
    "GPT-4o": "gpt-4o",
    "GPT-4o-mini": "gpt-4o-mini",
    "Claude-3.5-Sonnet": "claude-3-5-sonnet-20241022"
}

MAX_TOKENS_MAP = {
    "meta-llama/Llama-3.3-70B-Instruct": 900,
    "meta-llama/Llama-3.1-8B-Instruct": 700,
    "DeepSeek-R1": 8192,
    "o3-mini": 4096,
    "gpt-4o": 4096,
    "gpt-4o-mini": 4096,
    "claude-3-5-sonnet-20241022": 1024
}

# Modelos que usam OpenAI (GPT)
OPENAI_MODELS = {
    "o3-mini",
    "gpt-4o",
    "gpt-4o-mini"
}

# Modelos que usam Anthropic (Claude)
ANTHROPIC_MODELS = {
    "claude-3-5-sonnet-20241022"
}

# Configurações do agente
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "LLaMA 70B")
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "40"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0"))

# Configurações do Gradio
GRADIO_SHARE = os.getenv("GRADIO_SHARE", "False").lower() == "true"
GRADIO_PORT = int(os.getenv("GRADIO_PORT", "7860"))

# Configurações de logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Configuração do logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Cria diretório de upload se não existir
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Configuração das variáveis de ambiente para OpenAI
if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Configuração das variáveis de ambiente para Anthropic
if ANTHROPIC_API_KEY:
    os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY

def get_active_csv_path():
    """Retorna o CSV ativo: o carregado ou o padrão."""
    if os.path.exists(UPLOADED_CSV_PATH):
        logging.info(f"[CSV] Usando arquivo CSV carregado: {UPLOADED_CSV_PATH}")
        return UPLOADED_CSV_PATH
    else:
        logging.info(f"[CSV] Usando arquivo CSV padrão: {DEFAULT_CSV_PATH}")
        return DEFAULT_CSV_PATH

def validate_config():
    """Valida se as configurações necessárias estão presentes."""
    errors = []

    if not HUGGINGFACE_API_KEY:
        errors.append("HUGGINGFACE_API_KEY não configurada")

    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY não configurada")

    if not ANTHROPIC_API_KEY:
        errors.append("ANTHROPIC_API_KEY não configurada")

    if not os.path.exists(DEFAULT_CSV_PATH):
        errors.append(f"Arquivo CSV padrão não encontrado: {DEFAULT_CSV_PATH}")

    if errors:
        raise ValueError(f"Erros de configuração: {', '.join(errors)}")

    logging.info("Configurações validadas com sucesso")
    return True
