"""
Ferramentas para o agente SQL
"""
import time
import logging
from typing import Dict, Any, Optional, List
from huggingface_hub import InferenceClient
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
import pandas as pd

from utils.config import (
    HUGGINGFACE_API_KEY,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    LLAMA_MODELS,
    MAX_TOKENS_MAP,
    OPENAI_MODELS,
    ANTHROPIC_MODELS
)

# Cliente HuggingFace
hf_client = InferenceClient(
    provider="together",
    api_key=HUGGINGFACE_API_KEY
)

# Cliente OpenAI
openai_client = None
if OPENAI_API_KEY:
    openai_client = ChatOpenAI(
        api_key=OPENAI_API_KEY,
        temperature=0
    )

# Cliente Anthropic
anthropic_client = None
if ANTHROPIC_API_KEY:
    anthropic_client = ChatAnthropic(
        model="claude-3-5-sonnet-20241022",
        api_key=ANTHROPIC_API_KEY,
        temperature=0
    )

def generate_initial_context(db_sample: pd.DataFrame) -> str:
    """
    Gera contexto inicial para o modelo LLM

    Args:
        db_sample: Amostra dos dados do banco

    Returns:
        String com o contexto formatado
    """
    return (
        f"Você é um assistente especializado em gerar queries SQL precisas e otimizadas. Analise cuidadosamente a estrutura da tabela e a pergunta do usuário.\n\n"
        f"Exemplos do banco de dados:\n{db_sample.head().to_string(index=False)}\n\n"
        "\n***IMPORTANTE***: Detecte automaticamente o idioma da pergunta do usuário e responda sempre no mesmo idioma."

        "**REGRAS ESSENCIAIS**:\n"
        "2. Para buscar texto parcial use LIKE '%termo%'.\n"
        "3. Para NULL use IS NULL ou IS NOT NULL (nunca = NULL).\n"
        "4. Em agregações (SUM, COUNT, AVG) use GROUP BY nas colunas não agregadas.\n"
        "5. Para datas use formato 'YYYY-MM-DD' ou funções date() do SQLite.\n"
        "6. Nomes de colunas devem ser EXATAMENTE como mostrado.\n"

        "\n**INFORMAÇÕES IMPORTANTES**:\n"
        "- Detecte o idioma da pergunta e responda no mesmo idioma\n"
        "- Nunca altere nem abrevie a pergunta do usuário, sempre retorne-a no texto da resposta.\n"
        "- Gere a query que responda precisamente o que foi perguntado\n"
        "- Você está usando um banco de dados SQLite.\n"

        "\n***FORMATO DE RESPOSTA OBRIGATÓRIO***:\n"
        "Retorne EXATAMENTE no seguinte formato (sem histórico, sem informações extras):\n"
        "\nPergunta: <pergunta do usuário>\n"
        "\nQuery SQL:\n<query SQL>"
        "\nIdioma: <idioma>\n"
    )

def is_greeting(user_query: str) -> bool:
    """
    Verifica se a query do usuário é uma saudação
    
    Args:
        user_query: Query do usuário
        
    Returns:
        True se for saudação, False caso contrário
    """
    greetings = ["olá", "oi", "bom dia", "boa tarde", "boa noite", "oi, tudo bem?"]
    return user_query.lower().strip() in greetings

async def query_with_llama(
    user_query: str,
    db_sample: pd.DataFrame,
    selected_model_name: str,
    recent_history: List[Dict[str, str]] = None
) -> tuple[Optional[str], str]:
    """
    Consulta o modelo LLM (HuggingFace ou OpenAI) para gerar instruções SQL

    Args:
        user_query: Pergunta do usuário
        db_sample: Amostra dos dados do banco
        selected_model_name: Nome do modelo selecionado
        recent_history: Histórico recente de conversas

    Returns:
        Tupla com (resposta, model_id)
    """
    model_id = LLAMA_MODELS[selected_model_name]
    max_tokens = MAX_TOKENS_MAP.get(model_id, 512)

    if recent_history is None:
        recent_history = []

    initial_context = generate_initial_context(db_sample)

    # Constrói o prompt com histórico apenas como contexto interno
    if recent_history:
        formatted_history = "\n".join(
            [f"{msg['role'].capitalize()}: {msg['content']}" for msg in recent_history[-2:]]
        )

        full_prompt = (
            f"{initial_context}\n\n"
            f"Histórico recente:\n{formatted_history}\n\n"
            f"Pergunta do usuário:\n{user_query}\n\n"
        )
    else:
        full_prompt = f"{initial_context}\n\nPERGUNTA DO USUÁRIO:\n{user_query}"

    logging.info(f"[DEBUG] Contexto enviado ao ({selected_model_name}):\n{full_prompt}\n")

    start_time = time.time()

    try:
        # Verifica se é um modelo OpenAI (GPT)
        if model_id in OPENAI_MODELS:
            if not openai_client:
                raise ValueError("Cliente OpenAI não configurado. Verifique a OPENAI_API_KEY.")

            # Usa o cliente OpenAI
            response = openai_client.invoke([
                {"role": "system", "content": full_prompt}
            ])

            llm_response = response.content

        # Verifica se é um modelo Anthropic (Claude)
        elif model_id in ANTHROPIC_MODELS:
            if not anthropic_client:
                raise ValueError("Cliente Anthropic não configurado. Verifique a ANTHROPIC_API_KEY.")

            # Usa o cliente Anthropic
            response = anthropic_client.invoke([
                {"role": "user", "content": full_prompt}
            ])

            llm_response = response.content

        else:
            # Usa o cliente HuggingFace
            response = hf_client.chat.completions.create(
                model=model_id,
                messages=[{"role": "system", "content": full_prompt}],
                max_tokens=max_tokens,
                stream=False
            )

            llm_response = response["choices"][0]["message"]["content"]

        end_time = time.time()
        logging.info(f"[DEBUG] Resposta do {selected_model_name} para o Agent SQL:\n{llm_response.strip()}\n[Tempo de execução: {end_time - start_time:.2f}s]\n")
        return llm_response.strip(), model_id

    except Exception as e:
        logging.error(f"[ERRO] Falha ao interagir com o modelo {selected_model_name}: {e}")
        return None, model_id

async def refine_response_with_llm(
    user_question: str, 
    sql_response: str, 
    chart_md: str = ""
) -> str:
    """
    Refina a resposta usando um modelo LLM adicional
    
    Args:
        user_question: Pergunta original do usuário
        sql_response: Resposta do agente SQL
        chart_md: Markdown de gráficos (opcional)
        
    Returns:
        Resposta refinada
    """
    prompt = (
        f"Pergunta do usuário:\n{user_question}\n\n"
        f"Resposta gerada pelo agente SQL:\n{sql_response}\n\n"
        "Sua tarefa é refinar, complementar e melhorar a resposta.\n" 
        "Sempre mantenha a resposta original, o refinamento vem posteriormente."
    )

    logging.info(f"[DEBUG] Prompt enviado ao modelo de refinamento:\n{prompt}\n")

    try:
        response = hf_client.chat.completions.create(
            model=LLAMA_MODELS["LLaMA 70B"],
            messages=[{"role": "system", "content": prompt}],
            max_tokens=1200,
            stream=False
        )
        improved_response = response["choices"][0]["message"]["content"]
        logging.info(f"[DEBUG] Resposta do modelo de refinamento:\n{improved_response}\n")
        return improved_response + ("\n\n" + chart_md if chart_md else "")

    except Exception as e:
        logging.error(f"[ERRO] Falha ao refinar resposta com LLM: {e}")
        return sql_response + ("\n\n" + chart_md if chart_md else "")

class CacheManager:
    """Gerenciador de cache para queries"""
    
    def __init__(self):
        self.query_cache: Dict[str, str] = {}
        self.history_log: List[Dict[str, Any]] = []
        self.recent_history: List[Dict[str, str]] = []
    
    def get_cached_response(self, query: str) -> Optional[str]:
        """Obtém resposta do cache"""
        return self.query_cache.get(query)
    
    def cache_response(self, query: str, response: str):
        """Armazena resposta no cache"""
        self.query_cache[query] = response
    
    def add_to_history(self, entry: Dict[str, Any]):
        """Adiciona entrada ao histórico"""
        self.history_log.append(entry)
    
    def update_recent_history(self, user_input: str, response: str):
        """Atualiza histórico recente"""
        self.recent_history.append({"role": "user", "content": user_input})
        self.recent_history.append({"role": "assistant", "content": response})
        
        # Mantém apenas as últimas 4 entradas (2 pares pergunta-resposta)
        if len(self.recent_history) > 4:
            self.recent_history.pop(0)
            self.recent_history.pop(0)
    
    def clear_cache(self):
        """Limpa todo o cache"""
        self.query_cache.clear()
        self.history_log.clear()
        self.recent_history.clear()
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Retorna histórico completo"""
        return self.history_log
