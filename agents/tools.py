"""
Ferramentas para o agente SQL
"""
import time
import logging
import re
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
    AVAILABLE_MODELS,
    REFINEMENT_MODELS,
    LLAMA_MODELS,
    MAX_TOKENS_MAP,
    OPENAI_MODELS,
    ANTHROPIC_MODELS,
    HUGGINGFACE_MODELS
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

        "**REGRAS ESSENCIAIS**:\n"
        "2. Para buscar texto parcial use LIKE '%termo%'.\n"
        "3. Para NULL use IS NULL ou IS NOT NULL (nunca = NULL).\n"
        "4. Em agregações (SUM, COUNT, AVG) use GROUP BY nas colunas não agregadas.\n"
        "5. Para datas use formato 'YYYY-MM-DD' ou funções date() do SQLite.\n"
        "6. Nomes de colunas devem ser EXATAMENTE como mostrado.\n"
        "- Detecte o idioma da pergunta e responda no mesmo idioma\n"
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

def detect_query_type(user_query: str) -> str:
    """
    Detecta o tipo de processamento necessário para a query do usuário

    Args:
        user_query: Pergunta do usuário

    Returns:
        Tipo de processamento: 'sql_query', 'sql_query_graphic', 'prediction', 'chart'
    """
    query_lower = user_query.lower().strip()

    # Palavras-chave para diferentes tipos
    prediction_keywords = ['prever', 'predizer', 'previsão', 'forecast', 'predict', 'tendência', 'projeção']

    # Palavras-chave para gráficos - expandida para melhor detecção
    chart_keywords = [
        'gráfico', 'grafico', 'chart', 'plot', 'visualizar', 'visualização', 'visualizacao',
        'mostrar gráfico', 'mostrar grafico', 'gerar gráfico', 'gerar grafico',
        'criar gráfico', 'criar grafico', 'plotar', 'desenhar gráfico', 'desenhar grafico',
        'exibir gráfico', 'exibir grafico', 'fazer gráfico', 'fazer grafico',
        'gráfico de', 'grafico de', 'em gráfico', 'em grafico',
        'barras', 'linha', 'pizza', 'área', 'area', 'histograma',
        'scatter', 'dispersão', 'dispersao', 'boxplot', 'heatmap'
    ]

    # Verifica se há solicitação de gráfico
    has_chart_request = any(keyword in query_lower for keyword in chart_keywords)

    # Verifica se há solicitação de previsão
    has_prediction_request = any(keyword in query_lower for keyword in prediction_keywords)

    # Lógica de detecção
    if has_prediction_request:
        return 'prediction'  # Futuro: agente de ML/previsões
    elif has_chart_request:
        return 'sql_query_graphic'  # SQL + Gráfico
    else:
        return 'sql_query'  # SQL normal

def prepare_sql_context(user_query: str, db_sample: pd.DataFrame) -> str:
    """
    Prepara o contexto inicial para ser enviado diretamente ao agentSQL

    Args:
        user_query: Pergunta do usuário
        db_sample: Amostra dos dados do banco

    Returns:
        Contexto formatado para o agentSQL
    """
    # Usa o contexto base do generate_initial_context
    base_context = generate_initial_context(db_sample)

    context = (
        f"""
        Você é um assistente especializado em consultas SQL e análise de dados.

        REGRAS OBRIGATORIAS:
        - “Retorne os resultados da consulta em formato legível, sem incluir o texto da query SQL.”
        
        IMPORTANTE:
        - Responda SEMPRE em português brasileiro, independentemente do idioma da pergunta.
        - Mantenha suas respostas consistentes, claras e objetivas.
        - O nome da tabela é "tabela".
        - Realize TODOS os cálculos aritméticos diretamente dentro da query SQL.
        - NÃO realize cálculos fora da query.
        - Use funções SQL como AVG, SUM, COUNT, MAX, MIN, CASE WHEN, etc., conforme necessário.
        """
        "\n\n"
        f"**PERGUNTA DO USUÁRIO**:\n{user_query}"
    )

    return context

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
        "Sua tarefa é refinar a resposta para deixá-la mais clara, completa e compreensível em português, "
        "mantendo a resposta original no início do texto e adicionando insights úteis sobre logística de entregas de produtos, "
        "por exemplo: comparar com padrões típicos, identificar possíveis problemas ou sugerir ações para melhorar atrasos, performance ou custos. "
        "Evite repetir informações sem necessidade e não invente dados."
    )

    logging.info(f"[DEBUG] Prompt enviado ao modelo de refinamento:\n{prompt}\n")

    try:
        response = hf_client.chat.completions.create(
            model=REFINEMENT_MODELS["LLaMA 70B"],
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

# ==================== FUNÇÕES DE GRÁFICOS ====================

def generate_graph_type_context(user_query: str, sql_query: str, df_columns: List[str], df_sample: pd.DataFrame) -> str:
    """
    Gera contexto para LLM escolher o tipo de gráfico mais adequado

    Args:
        user_query: Pergunta original do usuário
        sql_query: Query SQL gerada pelo agente
        df_columns: Lista de colunas retornadas pela query
        df_sample: Amostra dos dados para análise

    Returns:
        Contexto formatado para a LLM
    """
    # Criar uma descrição detalhada dos dados para ajudar a LLM a entender melhor a estrutura
    data_description = ""
    if not df_sample.empty:
        # Verificar tipos de dados de forma mais robusta
        numeric_cols = []
        date_cols = []
        categorical_cols = []

        for col in df_sample.columns:
            col_data = df_sample[col]

            # Verifica se é numérico (incluindo strings que representam números)
            try:
                # Tenta converter para numérico, tratando vírgulas como separador decimal
                if col_data.dtype == 'object':
                    test_numeric = pd.to_numeric(col_data.astype(str).str.replace(',', '.'), errors='coerce')
                    if test_numeric.notna().sum() > len(col_data) * 0.8:  # 80% são números válidos
                        numeric_cols.append(col)
                    else:
                        categorical_cols.append(col)
                elif pd.api.types.is_numeric_dtype(col_data):
                    numeric_cols.append(col)
                elif pd.api.types.is_datetime64_any_dtype(col_data) or 'data' in col.lower():
                    date_cols.append(col)
                else:
                    categorical_cols.append(col)
            except:
                categorical_cols.append(col)

        # Adicionar informações sobre os primeiros valores de cada coluna
        data_description = "\nAmostra dos dados (primeiras 3 linhas):\n"
        data_description += df_sample.head(3).to_string(index=False)

        # Adicionar análise detalhada dos tipos de dados
        data_description += f"\n\nAnálise dos dados ({len(df_sample)} linhas total):"
        data_description += f"\n- Total de colunas: {len(df_sample.columns)}"

        if numeric_cols:
            data_description += f"\n- Colunas NUMÉRICAS ({len(numeric_cols)}): {', '.join(numeric_cols)}"
            # Adiciona informação sobre valores numéricos
            for col in numeric_cols[:2]:  # Máximo 2 colunas para não ficar muito longo
                try:
                    if df_sample[col].dtype == 'object':
                        # Converte strings para números
                        numeric_values = pd.to_numeric(df_sample[col].astype(str).str.replace(',', '.'), errors='coerce')
                        min_val, max_val = numeric_values.min(), numeric_values.max()
                    else:
                        min_val, max_val = df_sample[col].min(), df_sample[col].max()
                    data_description += f"\n  • {col}: valores de {min_val} a {max_val}"
                except:
                    pass

        if date_cols:
            data_description += f"\n- Colunas de DATA/TEMPO ({len(date_cols)}): {', '.join(date_cols)}"

        if categorical_cols:
            data_description += f"\n- Colunas CATEGÓRICAS ({len(categorical_cols)}): {', '.join(categorical_cols)}"
            # Adiciona informação sobre categorias únicas
            for col in categorical_cols[:3]:  # Máximo 3 colunas
                unique_count = df_sample[col].nunique()
                data_description += f"\n  • {col}: {unique_count} valores únicos"

            # Destaque especial para múltiplas categóricas importantes
            if len(categorical_cols) >= 2 and len(numeric_cols) >= 1:
                data_description += f"\n\n⚠️ ATENÇÃO: {len(categorical_cols)} colunas categóricas + {len(numeric_cols)} numérica(s) → CONSIDERE GRÁFICO AGRUPADO (6) para mostrar múltiplas dimensões!"

    # Prompt ULTRA SIMPLIFICADO
    return (
        f"Escolha o gráfico mais adequado e de acordo com pergunta do usuário e os dados:\n\n"
        f"COLUNAS RETORNADAS: {', '.join(df_columns)}\n\n"
        f"DADOS: {data_description}\n\n"
        f"PERGUNTA: {user_query}\n\n"
        f"OPÇÕES DE GRÁFICOS::\n"
        f"1. Linha - evolução temporal\n"
        f"2. Multilinhas - múltiplas tendências\n"
        f"3. Área - volume temporal\n"
        f"4. Barras Verticais - comparar categorias (nomes curtos)\n"
        f"5. Barras Horizontais - comparar categorias (nomes longos)\n"
        f"6. Barras Agrupadas - múltiplas métricas\n"
        f"7. Barras Empilhadas - partes de um todo\n"
        f"8. Pizza - proporções (poucas categorias)\n"
        f"9. Dona - proporções (muitas categorias)\n"
        f"10. Pizzas Múltiplas - proporções por grupos\n\n"
        f"Responda apenas o número (1-10)."
        "\n\nINSTRUÇÕES FINAIS:\n"
        "1. PRIMEIRO: Verifique se o usuário especificou um tipo de gráfico na pergunta do usuário\n"
        "2. SE SIM: Use o gráfico solicitado (consulte o mapeamento acima)\n"
        "3. SE NÃO: Escolha o gráfico mais adequado\n\n"
    )

def extract_sql_query_from_response(agent_response: str) -> Optional[str]:
    """
    Extrai a query SQL da resposta do agente SQL

    Args:
        agent_response: Resposta completa do agente SQL

    Returns:
        Query SQL extraída ou None se não encontrada
    """
    if not agent_response:
        return None

    # Padrões para encontrar SQL na resposta - ordem de prioridade
    sql_patterns = [
        # Padrão mais comum: ```sql ... ``` (multiline)
        r"```sql\s*(.*?)\s*```",
        # Padrão alternativo: ``` ... ``` com SELECT (multiline)
        r"```\s*(SELECT.*?)\s*```",
        # SELECT com múltiplas linhas até ponto e vírgula
        r"(SELECT\s+.*?;)",
        # SELECT com múltiplas linhas até quebra dupla ou final
        r"(SELECT\s+.*?)(?:\n\s*\n|\n\s*$|\n\s*Agora|\n\s*Em seguida)",
        # Padrões com prefixos específicos
        r"Query:\s*(SELECT.*?)(?:\n|$|;)",
        r"SQL:\s*(SELECT.*?)(?:\n|$|;)",
        r"Consulta:\s*(SELECT.*?)(?:\n|$|;)",
        # SELECT em uma linha
        r"(SELECT\s+[^\n]+)",
    ]

    for i, pattern in enumerate(sql_patterns):
        matches = re.findall(pattern, agent_response, re.DOTALL | re.IGNORECASE)
        if matches:
            # Pega a primeira query encontrada
            query = matches[0].strip()

            # Limpa a query
            query = clean_sql_query(query)

            # Verifica se é uma query válida
            if is_valid_sql_query(query):
                logging.info(f"[GRAPH] Query SQL extraída (padrão {i+1}): {query[:100]}...")
                return query

    # Log da resposta para debug se não encontrar SQL
    logging.warning(f"[GRAPH] Não foi possível extrair query SQL. Resposta (primeiros 200 chars): {agent_response[:200]}...")
    return None

def clean_sql_query(query: str) -> str:
    """
    Limpa e normaliza a query SQL extraída

    Args:
        query: Query SQL bruta

    Returns:
        Query SQL limpa
    """
    if not query:
        return ""

    # Remove espaços extras e quebras de linha desnecessárias
    query = re.sub(r'\s+', ' ', query.strip())

    # Remove ponto e vírgula no final se existir
    if query.endswith(';'):
        query = query[:-1].strip()

    # Remove aspas ou caracteres especiais no início/fim
    query = query.strip('`"\'')

    return query

def is_valid_sql_query(query: str) -> bool:
    """
    Verifica se a string é uma query SQL válida

    Args:
        query: String para verificar

    Returns:
        True se for uma query SQL válida
    """
    if not query or len(query.strip()) < 6:  # Mínimo para "SELECT"
        return False

    # Verifica se começa com comando SQL válido
    sql_commands = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH']
    query_upper = query.strip().upper()

    return any(query_upper.startswith(cmd) for cmd in sql_commands)
