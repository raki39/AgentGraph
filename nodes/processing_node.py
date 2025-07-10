"""
Nó para processamento de contexto inicial usando Processing Agent
"""
import logging
import pandas as pd
from typing import Dict, Any

from agents.processing_agent import ProcessingAgentManager
from agents.tools import prepare_processing_context
from utils.object_manager import get_object_manager


async def process_initial_context_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nó para processar contexto inicial com Processing Agent (opcional)
    
    Args:
        state: Estado atual do agente
        
    Returns:
        Estado atualizado com contexto processado
    """
    # Verifica se o processing está habilitado
    processing_enabled = state.get("processing_enabled", False)
    logging.info(f"[PROCESSING NODE] Processing enabled: {processing_enabled}")

    if not processing_enabled:
        logging.info("[PROCESSING NODE] Processing Agent desabilitado - pulando nó")
        return state

    logging.info("[PROCESSING NODE] ===== INICIANDO NÓ DE PROCESSAMENTO =====")
    
    try:
        user_input = state.get("user_input", "")
        processing_model = state.get("processing_model", "gpt-4o-mini")

        logging.info(f"[PROCESSING NODE] Entrada do usuário: {user_input[:100]}...")
        logging.info(f"[PROCESSING NODE] Modelo selecionado: {processing_model}")

        if not user_input:
            logging.warning("[PROCESSING NODE] Entrada do usuário não disponível")
            return state
        
        # Acessa diretamente o banco de dados para criar amostra
        obj_manager = get_object_manager()

        # Usa os IDs do GraphManager (que são globais)
        try:
            # Acessa diretamente os IDs do GraphManager através do ObjectManager
            # Pega o primeiro engine e database disponíveis (assumindo que há apenas um)
            engines = obj_manager._engines
            databases = obj_manager._databases

            if not engines or not databases:
                logging.error("[PROCESSING NODE] Nenhum engine ou database encontrado no ObjectManager")
                return state

            # Pega o primeiro engine e database disponíveis
            engine_id = list(engines.keys())[0]
            db_id = list(databases.keys())[0]

            engine = engines[engine_id]
            database = databases[db_id]

            logging.info(f"[PROCESSING NODE] Usando engine {engine_id} e database {db_id}")

            # Cria amostra diretamente do banco
            import sqlalchemy as sa
            with engine.connect() as conn:
                # Obtém amostra de dados (10 linhas)
                result = conn.execute(sa.text("SELECT * FROM tabela LIMIT 10"))
                columns = result.keys()
                rows = result.fetchall()

                # Converte para DataFrame
                db_sample = pd.DataFrame(rows, columns=columns)

                logging.info(f"[PROCESSING NODE] Amostra criada diretamente do banco: {db_sample.shape[0]} linhas, {db_sample.shape[1]} colunas")
                logging.info(f"[PROCESSING NODE] Colunas: {list(db_sample.columns)}")

        except Exception as e:
            logging.error(f"[PROCESSING NODE] Erro ao acessar banco de dados: {e}")
            logging.error(f"[PROCESSING NODE] Detalhes do erro: {str(e)}")
            return state
        
        # Recupera ou cria Processing Agent
        processing_agent_id = state.get("processing_agent_id")
        
        if processing_agent_id:
            processing_agent = obj_manager.get_processing_agent(processing_agent_id)
            # Verifica se precisa recriar com modelo diferente
            if processing_agent and processing_agent.model_name != processing_model:
                logging.info(f"[PROCESSING NODE] Recriando Processing Agent com modelo {processing_model}")
                processing_agent.recreate_llm(processing_model)
            else:
                logging.info(f"[PROCESSING NODE] Reutilizando Processing Agent existente com modelo {processing_agent.model_name}")
        else:
            # Cria novo Processing Agent
            logging.info(f"[PROCESSING NODE] Criando novo Processing Agent com modelo {processing_model}")
            processing_agent = ProcessingAgentManager(processing_model)
            processing_agent_id = obj_manager.store_processing_agent(processing_agent)
            state["processing_agent_id"] = processing_agent_id
            logging.info(f"[PROCESSING NODE] Novo Processing Agent criado e armazenado com ID: {processing_agent_id}")
        
        # Prepara contexto para o Processing Agent
        processing_context = prepare_processing_context(user_input, db_sample)

        logging.info(f"[PROCESSING NODE] ===== CONTEXTO PARA PRIMEIRA LLM =====")
        logging.info(f"{processing_context}")
        logging.info(f"[PROCESSING NODE] ===== FIM DO CONTEXTO =====")
        
        # Executa processamento
        processing_result = await processing_agent.process_context(processing_context)

        # Log da resposta da primeira LLM
        logging.info(f"[PROCESSING NODE] ===== RESPOSTA DA PRIMEIRA LLM =====")
        logging.info(f"{processing_result.get('output', 'Sem resposta')}")
        logging.info(f"[PROCESSING NODE] ===== FIM DA RESPOSTA =====")

        if processing_result["success"]:
            # Extrai query sugerida e observações
            suggested_query = processing_result.get("suggested_query", "")
            query_observations = processing_result.get("query_observations", "")

            # Atualiza estado com resultados do processamento
            state.update({
                "suggested_query": suggested_query,
                "query_observations": query_observations,
                "processing_result": processing_result,
                "processing_success": True
            })
            
            # Log simples do resultado
            if suggested_query:
                logging.info(f"[PROCESSING NODE] ✅ Query SQL extraída com sucesso")
                logging.info(f"[PROCESSING NODE] ✅ Observações extraídas: {len(query_observations)} caracteres")
                logging.info(f"[PROCESSING NODE] 🎯 Query será incluída no contexto do SQL Agent")
            else:
                logging.warning(f"[PROCESSING NODE] ❌ Nenhuma query foi extraída - agente SQL funcionará normalmente")
            
        else:
            # Em caso de erro, continua sem processamento
            error_msg = processing_result.get("output", "Erro desconhecido")
            logging.error(f"[PROCESSING] Erro no processamento: {error_msg}")

            state.update({
                "suggested_query": "",
                "query_observations": "",
                "processing_result": processing_result,
                "processing_success": False,
                "processing_error": error_msg
            })
        
    except Exception as e:
        error_msg = f"Erro no nó de processamento: {e}"
        logging.error(f"[PROCESSING] {error_msg}")
        
        # Em caso de erro, continua sem processamento
        state.update({
            "suggested_query": "",
            "query_observations": "",
            "processing_success": False,
            "processing_error": error_msg
        })
    
    return state


def should_use_processing(state: Dict[str, Any]) -> str:
    """
    Determina se deve usar o Processing Agent
    
    Args:
        state: Estado atual
        
    Returns:
        Nome do próximo nó
    """
    if state.get("processing_enabled", False):
        return "process_initial_context"
    else:
        return "prepare_context"


async def validate_processing_input_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valida entrada para o Processing Agent

    Args:
        state: Estado atual

    Returns:
        Estado validado
    """
    try:
        logging.info("[PROCESSING VALIDATION] ===== VALIDANDO ENTRADA PARA PROCESSING AGENT =====")

        # Verifica se processing está habilitado
        processing_enabled = state.get("processing_enabled", False)
        logging.info(f"[PROCESSING VALIDATION] Processing habilitado: {processing_enabled}")

        if not processing_enabled:
            logging.info("[PROCESSING VALIDATION] Processing desabilitado - pulando validação")
            return state

        # Valida modelo de processamento
        processing_model = state.get("processing_model", "")
        logging.info(f"[PROCESSING VALIDATION] Modelo especificado: '{processing_model}'")

        if not processing_model:
            logging.warning("[PROCESSING VALIDATION] Modelo de processamento não especificado, usando padrão")
            state["processing_model"] = "gpt-4o-mini"
            logging.info(f"[PROCESSING VALIDATION] Modelo padrão definido: gpt-4o-mini")

        # Valida entrada do usuário
        user_input = state.get("user_input", "")
        if not user_input or not user_input.strip():
            logging.error("[PROCESSING VALIDATION] Entrada do usuário vazia - desabilitando processing")
            state["processing_enabled"] = False
            return state

        logging.info(f"[PROCESSING VALIDATION] Validação concluída com sucesso")
        logging.info(f"[PROCESSING VALIDATION] Modelo final: {state['processing_model']}")
        logging.info(f"[PROCESSING VALIDATION] Entrada: {user_input[:100]}...")

    except Exception as e:
        logging.error(f"[PROCESSING VALIDATION] Erro na validação: {e}")
        state["processing_enabled"] = False

    return state
