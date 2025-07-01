"""
Nó para seleção do tipo de gráfico usando LLM
"""
import logging
import re
import pandas as pd
from typing import Dict, Any

from agents.tools import (
    generate_graph_type_context, 
    extract_sql_query_from_response,
    get_graph_type_mapping,
    hf_client
)
from utils.config import REFINEMENT_MODELS
from utils.object_manager import get_object_manager

async def graph_selection_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nó para seleção do tipo de gráfico usando LLM
    
    Args:
        state: Estado atual do agente
        
    Returns:
        Estado atualizado com tipo de gráfico selecionado
    """
    try:
        logging.info("[GRAPH_SELECTION] Iniciando seleção de tipo de gráfico")
        
        # Verifica se deve gerar gráfico
        query_type = state.get("query_type", "sql_query")
        if query_type != "sql_query_graphic":
            logging.info("[GRAPH_SELECTION] Tipo de query não requer gráfico, pulando seleção")
            return state
        
        # Usa query SQL capturada pelo handler (método mais confiável)
        sql_query = state.get("sql_query_extracted")

        if not sql_query:
            # Fallback: tenta extrair da resposta (método antigo)
            agent_response = state.get("response", "")
            logging.warning(f"[GRAPH_SELECTION] ⚠️ Handler não capturou SQL, tentando fallback...")
            sql_query = extract_sql_query_from_response(agent_response)

        if not sql_query:
            error_msg = "Não foi possível obter query SQL (nem pelo handler nem pela resposta)"
            logging.error(f"[GRAPH_SELECTION] ❌ {error_msg}")
            state.update({
                "graph_error": error_msg,
                "graph_generated": False
            })
            return state

        state["sql_query_extracted"] = sql_query
        logging.info(f"[GRAPH_SELECTION] 🔍 Usando Query SQL:\n{sql_query}")
        
        # Recupera dados do banco para análise
        obj_manager = get_object_manager()
        engine_id = state.get("engine_id")
        
        if not engine_id:
            error_msg = "ID do engine não encontrado"
            logging.error(f"[GRAPH_SELECTION] {error_msg}")
            state.update({
                "graph_error": error_msg,
                "graph_generated": False
            })
            return state
        
        engine = obj_manager.get_engine(engine_id)
        if not engine:
            error_msg = "Engine não encontrada no ObjectManager"
            logging.error(f"[GRAPH_SELECTION] {error_msg}")
            state.update({
                "graph_error": error_msg,
                "graph_generated": False
            })
            return state
        
        # Executa query para obter dados
        try:
            df_result = pd.read_sql_query(sql_query, engine)
            logging.info(f"[GRAPH_SELECTION] Dados obtidos: {len(df_result)} linhas, {len(df_result.columns)} colunas")
            
            if df_result.empty:
                error_msg = "Query SQL retornou dados vazios"
                logging.warning(f"[GRAPH_SELECTION] {error_msg}")
                state.update({
                    "graph_error": error_msg,
                    "graph_generated": False
                })
                return state
            
        except Exception as e:
            error_msg = f"Erro ao executar query SQL: {e}"
            logging.error(f"[GRAPH_SELECTION] {error_msg}")
            state.update({
                "graph_error": error_msg,
                "graph_generated": False
            })
            return state
        
        # Prepara amostra dos dados para análise
        df_sample = df_result.head(3)
        
        # Gera contexto para LLM escolher tipo de gráfico
        user_query = state.get("user_input", "")
        graph_context = generate_graph_type_context(
            user_query, 
            sql_query, 
            df_result.columns.tolist(), 
            df_sample
        )
        
        logging.info(f"[GRAPH_SELECTION] Enviando contexto para LLM escolher tipo de gráfico")
        
        # Consulta LLM para escolher tipo de gráfico
        graph_type = await get_graph_type_with_llm(graph_context)
        
        if not graph_type:
            error_msg = "LLM não conseguiu determinar tipo de gráfico"
            logging.error(f"[GRAPH_SELECTION] {error_msg}")
            state.update({
                "graph_error": error_msg,
                "graph_generated": False
            })
            return state
        
        # Armazena dados do gráfico no ObjectManager
        graph_data_id = obj_manager.store_object(df_result, "graph_data")
        
        # Atualiza estado com informações do gráfico
        state.update({
            "graph_type": graph_type,
            "graph_data": {
                "data_id": graph_data_id,
                "columns": df_result.columns.tolist(),
                "rows": len(df_result),
                "sample": df_sample.to_dict()
            },
            "graph_error": None
        })
        
        logging.info(f"[GRAPH_SELECTION] Tipo de gráfico selecionado: {graph_type}")
        
    except Exception as e:
        error_msg = f"Erro na seleção de gráfico: {e}"
        logging.error(f"[GRAPH_SELECTION] {error_msg}")
        state.update({
            "graph_error": error_msg,
            "graph_generated": False
        })
    
    return state

async def get_graph_type_with_llm(graph_context: str) -> str:
    """
    Consulta LLM para determinar o tipo de gráfico mais adequado
    
    Args:
        graph_context: Contexto formatado para a LLM
        
    Returns:
        Tipo de gráfico selecionado
    """
    try:
        # Usa modelo de refinamento para escolha do gráfico
        response = hf_client.chat.completions.create(
            model=REFINEMENT_MODELS["LLaMA 70B"],
            messages=[{"role": "system", "content": graph_context}],
            max_tokens=10,
            stream=False
        )
        
        llm_response = response["choices"][0]["message"]["content"].strip()
        logging.info(f"[GRAPH_SELECTION] Resposta da LLM: {llm_response}")
        
        # Mapear a resposta numérica para o tipo de gráfico
        graph_type_map = get_graph_type_mapping()
        
        # Extrair apenas o número da resposta
        match = re.search(r"\b([1-9]|10)\b", llm_response)
        if match:
            graph_number = match.group(0)
            graph_type = graph_type_map.get(graph_number, "bar_vertical")
            logging.info(f"[GRAPH_SELECTION] Tipo escolhido: {graph_type} (número {graph_number})")
            return graph_type
        else:
            logging.warning("[GRAPH_SELECTION] Não foi possível extrair número válido da resposta")
            return "bar_vertical"  # Default
            
    except Exception as e:
        logging.error(f"[GRAPH_SELECTION] Erro ao consultar LLM: {e}")
        return "bar_vertical"  # Default em caso de erro
