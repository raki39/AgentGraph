"""
Nó principal do agente SQL para LangGraph - Versão refatorada
"""
import logging
from typing import Dict, Any, TypedDict, Optional

from utils.object_manager import get_object_manager

class AgentState(TypedDict):
    """Estado do agente LangGraph - apenas dados serializáveis"""
    user_input: str
    selected_model: str
    response: str
    advanced_mode: bool
    execution_time: float
    error: Optional[str]
    intermediate_steps: list
    # Dados serializáveis do banco
    db_sample_dict: dict
    # IDs para recuperar objetos não-serializáveis
    agent_id: str
    engine_id: str
    cache_id: str

async def initialize_agent_components_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nó para inicializar componentes do agente

    Args:
        state: Estado inicial

    Returns:
        Estado com componentes inicializados
    """
    try:
        obj_manager = get_object_manager()

        # Verifica se os IDs necessários estão presentes
        required_ids = ["agent_id", "engine_id", "cache_id"]
        for id_name in required_ids:
            if not state.get(id_name):
                raise ValueError(f"ID necessário não encontrado: {id_name}")

        # Verifica se os objetos existem
        sql_agent = obj_manager.get_sql_agent(state["agent_id"])
        engine = obj_manager.get_engine(state["engine_id"])
        cache_manager = obj_manager.get_cache_manager(state["cache_id"])

        if not all([sql_agent, engine, cache_manager]):
            raise ValueError("Um ou mais componentes não foram encontrados")

        state["components_ready"] = True
        logging.info("[AGENT] Componentes inicializados com sucesso")

    except Exception as e:
        error_msg = f"Erro ao inicializar componentes: {e}"
        logging.error(f"[AGENT] {error_msg}")
        state["error"] = error_msg
        state["components_ready"] = False

    return state

def should_refine_response(state: Dict[str, Any]) -> str:
    """
    Função condicional para determinar se deve refinar a resposta

    Args:
        state: Estado atual do agente

    Returns:
        Nome do próximo nó
    """
    if state.get("advanced_mode", False) and not state.get("error"):
        return "refine_response"
    else:
        return "cache_response"

class AgentNodeManager:
    """
    Gerenciador dos nós do agente - versão refatorada
    """

    def __init__(self):
        self.node_functions = {
            "initialize_components": initialize_agent_components_node
        }
        self.conditional_functions = {
            "should_refine": should_refine_response
        }

    def get_node_function(self, node_name: str):
        """Retorna função do nó pelo nome"""
        return self.node_functions.get(node_name)

    def get_conditional_function(self, condition_name: str):
        """Retorna função condicional pelo nome"""
        return self.conditional_functions.get(condition_name)
