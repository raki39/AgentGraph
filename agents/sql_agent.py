"""
Criação e configuração do agente SQL
"""
import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.utilities import SQLDatabase

from utils.config import MAX_ITERATIONS, TEMPERATURE

def create_sql_agent_executor(db: SQLDatabase, model_name: str = "gpt-4o-mini"):
    """
    Cria um agente SQL usando LangChain
    
    Args:
        db: Objeto SQLDatabase do LangChain
        model_name: Nome do modelo OpenAI a usar
        
    Returns:
        Agente SQL configurado
    """
    try:
        # Cria o modelo LLM
        llm = ChatOpenAI(
            model=model_name, 
            temperature=TEMPERATURE
        )
        
        # Cria o agente SQL
        sql_agent = create_sql_agent(
            llm=llm,
            db=db,
            agent_type="openai-tools",
            verbose=True,
            max_iterations=MAX_ITERATIONS,
            return_intermediate_steps=True
        )
        
        logging.info(f"Agente SQL criado com sucesso usando modelo {model_name}")
        return sql_agent
        
    except Exception as e:
        logging.error(f"Erro ao criar agente SQL: {e}")
        raise

class SQLAgentManager:
    """
    Gerenciador do agente SQL com funcionalidades avançadas
    """
    
    def __init__(self, db: SQLDatabase, model_name: str = "gpt-4o-mini"):
        self.db = db
        self.model_name = model_name
        self.agent = None
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Inicializa o agente SQL"""
        self.agent = create_sql_agent_executor(self.db, self.model_name)
    
    def recreate_agent(self, new_db: SQLDatabase = None, new_model: str = None):
        """
        Recria o agente com novos parâmetros
        
        Args:
            new_db: Novo banco de dados (opcional)
            new_model: Novo modelo (opcional)
        """
        if new_db:
            self.db = new_db
        if new_model:
            self.model_name = new_model
        
        self._initialize_agent()
        logging.info("Agente SQL recriado com sucesso")
    
    async def execute_query(self, instruction: str) -> dict:
        """
        Executa uma query através do agente SQL
        
        Args:
            instruction: Instrução para o agente
            
        Returns:
            Resultado da execução
        """
        try:
            logging.info("------- Agent SQL: Executando query -------")
            response = self.agent.invoke({"input": instruction})
            
            result = {
                "output": response.get("output", "Erro ao obter a resposta do agente."),
                "intermediate_steps": response.get("intermediate_steps", []),
                "success": True
            }
            
            logging.info(f"Query executada com sucesso: {result['output'][:100]}...")
            return result
            
        except Exception as e:
            error_msg = f"Erro ao consultar o agente SQL: {e}"
            logging.error(error_msg)
            return {
                "output": error_msg,
                "intermediate_steps": [],
                "success": False
            }
    
    def get_agent_info(self) -> dict:
        """
        Retorna informações sobre o agente atual
        
        Returns:
            Dicionário com informações do agente
        """
        return {
            "model_name": self.model_name,
            "max_iterations": MAX_ITERATIONS,
            "temperature": TEMPERATURE,
            "database_tables": self.db.get_usable_table_names() if self.db else [],
            "agent_type": "openai-tools"
        }
    
    def validate_agent(self) -> bool:
        """
        Valida se o agente está funcionando corretamente
        
        Returns:
            True se válido, False caso contrário
        """
        try:
            # Testa com uma query simples
            test_result = self.agent.invoke({
                "input": "Quantas linhas existem na tabela?"
            })
            
            success = "output" in test_result and test_result["output"]
            logging.info(f"Validação do agente: {'Sucesso' if success else 'Falha'}")
            return success
            
        except Exception as e:
            logging.error(f"Erro na validação do agente: {e}")
            return False

def get_default_sql_agent(db: SQLDatabase) -> SQLAgentManager:
    """
    Cria um agente SQL com configurações padrão
    
    Args:
        db: Objeto SQLDatabase
        
    Returns:
        SQLAgentManager configurado
    """
    return SQLAgentManager(db)
