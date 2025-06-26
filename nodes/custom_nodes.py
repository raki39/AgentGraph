"""
Nós personalizados para funcionalidades específicas
"""
import os
import shutil
import logging
from typing import Dict, Any, TypedDict

from utils.database import create_sql_database
from utils.config import UPLOADED_CSV_PATH, SQL_DB_PATH, DEFAULT_CSV_PATH
from agents.sql_agent import SQLAgentManager
from nodes.csv_processing_node import csv_processing_node
from nodes.database_node import create_database_from_dataframe_node, load_existing_database_node

class FileUploadState(TypedDict):
    """Estado para upload de arquivos"""
    file_path: str
    success: bool
    message: str
    engine: Any
    sql_agent: SQLAgentManager
    cache_manager: Any

class ResetState(TypedDict):
    """Estado para reset do sistema"""
    success: bool
    message: str
    engine: Any
    sql_agent: SQLAgentManager
    cache_manager: Any

async def handle_csv_upload_node(state: FileUploadState) -> FileUploadState:
    """
    Nó para processar upload de CSV
    
    Args:
        state: Estado do upload
        
    Returns:
        Estado atualizado
    """
    try:
        file_path = state["file_path"]
        
        # Etapa 1: Processa CSV usando nova arquitetura
        csv_state = {
            "file_path": file_path,
            "success": False,
            "message": "",
            "csv_data_sample": {},
            "column_info": {},
            "processing_stats": {}
        }

        csv_result = await csv_processing_node(csv_state)
        if not csv_result["success"]:
            raise Exception(csv_result["message"])

        # Etapa 2: Cria banco de dados
        db_result = await create_database_from_dataframe_node(csv_result)
        if not db_result["success"]:
            raise Exception(db_result["message"])

        # Recupera objetos criados
        from utils.object_manager import get_object_manager
        obj_manager = get_object_manager()

        engine = obj_manager.get_engine(db_result["engine_id"])
        db = obj_manager.get_object(db_result["db_id"])

        logging.info("[UPLOAD] Novo banco carregado e DB atualizado usando nova arquitetura.")

        # Recria agente SQL
        sql_agent = SQLAgentManager(db)
        
        # Limpa cache
        state["cache_manager"].clear_cache()
        
        # Atualiza estado
        state["engine"] = engine
        state["sql_agent"] = sql_agent
        state["success"] = True
        state["message"] = "✅ CSV carregado com sucesso!"
        
        logging.info("[UPLOAD] Novo banco carregado e agente recriado. Cache limpo.")
        
    except Exception as e:
        error_msg = f"❌ Erro ao processar CSV: {e}"
        logging.error(f"[ERRO] Falha ao processar novo CSV: {e}")
        state["success"] = False
        state["message"] = error_msg
    
    return state

async def reset_system_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nó para resetar o sistema ao estado inicial

    Args:
        state: Estado do reset

    Returns:
        Estado atualizado
    """
    try:
        from utils.object_manager import get_object_manager
        from agents.sql_agent import SQLAgentManager

        obj_manager = get_object_manager()

        # Remove CSV personalizado se existir
        if os.path.exists(UPLOADED_CSV_PATH):
            os.remove(UPLOADED_CSV_PATH)
            logging.info("[RESET] CSV personalizado removido.")

        # Recria banco com CSV padrão usando nova arquitetura
        csv_state = {
            "file_path": DEFAULT_CSV_PATH,
            "success": False,
            "message": "",
            "csv_data_sample": {},
            "column_info": {},
            "processing_stats": {}
        }

        csv_result = await csv_processing_node(csv_state)
        if not csv_result["success"]:
            raise Exception(csv_result["message"])

        # Cria banco de dados
        db_result = await create_database_from_dataframe_node(csv_result)
        if not db_result["success"]:
            raise Exception(db_result["message"])

        # Recupera objetos criados
        engine = obj_manager.get_engine(db_result["engine_id"])
        db = obj_manager.get_object(db_result["db_id"])

        # Recria agente SQL
        sql_agent = SQLAgentManager(db)

        # Atualiza objetos no gerenciador
        engine_id = obj_manager.store_engine(engine)
        agent_id = obj_manager.store_sql_agent(sql_agent)

        # Limpa cache se disponível
        cache_id = state.get("cache_id")
        if cache_id:
            cache_manager = obj_manager.get_cache_manager(cache_id)
            if cache_manager:
                cache_manager.clear_cache()

        # Atualiza estado
        state.update({
            "engine_id": engine_id,
            "agent_id": agent_id,
            "success": True,
            "message": "🔄 Sistema resetado para o estado inicial."
        })

        logging.info("[RESET] Sistema resetado com sucesso.")

    except Exception as e:
        error_msg = f"❌ Erro ao resetar: {e}"
        logging.error(f"[ERRO] Falha ao resetar sistema: {e}")
        state.update({
            "success": False,
            "message": error_msg
        })

    return state

async def validate_system_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nó para validar o estado do sistema
    
    Args:
        state: Estado atual do sistema
        
    Returns:
        Estado com informações de validação
    """
    validation_results = {
        "database_valid": False,
        "agent_valid": False,
        "cache_valid": False,
        "overall_valid": False
    }
    
    try:
        # Valida banco de dados
        if state.get("engine"):
            from utils.database import validate_database
            validation_results["database_valid"] = validate_database(state["engine"])
        
        # Valida agente SQL
        if state.get("sql_agent"):
            validation_results["agent_valid"] = state["sql_agent"].validate_agent()
        
        # Valida cache
        if state.get("cache_manager"):
            validation_results["cache_valid"] = True  # Cache sempre válido se existe
        
        # Validação geral
        validation_results["overall_valid"] = all([
            validation_results["database_valid"],
            validation_results["agent_valid"],
            validation_results["cache_valid"]
        ])
        
        state["validation"] = validation_results
        logging.info(f"[VALIDATION] Sistema válido: {validation_results['overall_valid']}")
        
    except Exception as e:
        logging.error(f"[VALIDATION] Erro na validação: {e}")
        state["validation"] = validation_results
    
    return state

async def get_system_info_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nó para obter informações do sistema
    
    Args:
        state: Estado atual do sistema
        
    Returns:
        Estado com informações do sistema
    """
    system_info = {
        "csv_active": None,
        "database_path": SQL_DB_PATH,
        "agent_info": None,
        "cache_stats": None
    }
    
    try:
        # Informações do CSV ativo
        from utils.config import get_active_csv_path
        system_info["csv_active"] = get_active_csv_path()
        
        # Informações do agente
        if state.get("sql_agent"):
            system_info["agent_info"] = state["sql_agent"].get_agent_info()
        
        # Estatísticas do cache
        if state.get("cache_manager"):
            cache_manager = state["cache_manager"]
            system_info["cache_stats"] = {
                "cached_queries": len(cache_manager.query_cache),
                "history_entries": len(cache_manager.history_log),
                "recent_history_size": len(cache_manager.recent_history)
            }
        
        state["system_info"] = system_info
        logging.info("[SYSTEM_INFO] Informações do sistema coletadas")
        
    except Exception as e:
        logging.error(f"[SYSTEM_INFO] Erro ao coletar informações: {e}")
        state["system_info"] = system_info
    
    return state

class CustomNodeManager:
    """
    Gerenciador dos nós personalizados
    """
    
    def __init__(self):
        self.node_functions = {
            "csv_upload": handle_csv_upload_node,
            "system_reset": reset_system_node,
            "system_validation": validate_system_node,
            "system_info": get_system_info_node
        }
    
    def get_node_function(self, node_name: str):
        """Retorna função do nó pelo nome"""
        return self.node_functions.get(node_name)
    
    async def execute_node(self, node_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa um nó específico
        
        Args:
            node_name: Nome do nó
            state: Estado atual
            
        Returns:
            Estado atualizado
        """
        node_function = self.get_node_function(node_name)
        if node_function:
            return await node_function(state)
        else:
            logging.error(f"Nó não encontrado: {node_name}")
            return state
