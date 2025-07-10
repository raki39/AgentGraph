"""
Grafo principal do LangGraph para o AgentGraph
"""
import logging
import pandas as pd
import re
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import Integer, Float, DateTime

from nodes.agent_node import (
    AgentState,
    should_refine_response,
    should_generate_graph,
    should_use_processing_agent,
    route_after_cache_check
)
from nodes.csv_processing_node import csv_processing_node
from nodes.database_node import (
    create_database_from_dataframe_node,
    load_existing_database_node,
    get_database_sample_node
)
from nodes.query_node import (
    validate_query_input_node,
    prepare_query_context_node,
    process_user_query_node
)
from nodes.refinement_node import (
    refine_response_node,
    format_final_response_node
)
from nodes.processing_node import (
    process_initial_context_node,
    validate_processing_input_node
)
from nodes.cache_node import (
    check_cache_node,
    cache_response_node,
    update_history_node
)
from nodes.graph_selection_node import graph_selection_node
from nodes.graph_generation_node import graph_generation_node
from nodes.custom_nodes import CustomNodeManager
from agents.sql_agent import SQLAgentManager
from agents.tools import CacheManager
from utils.database import create_sql_database
from utils.config import get_active_csv_path, SQL_DB_PATH
from utils.object_manager import get_object_manager

class AgentGraphManager:
    """
    Gerenciador principal do grafo LangGraph
    """
    
    def __init__(self):
        self.graph = None
        self.app = None
        self.cache_manager = CacheManager()
        self.custom_node_manager = CustomNodeManager()
        self.object_manager = get_object_manager()
        self.engine = None
        self.sql_agent = None
        self.db = None
        # IDs para objetos não-serializáveis
        self.agent_id = None
        self.engine_id = None
        self.db_id = None
        self.cache_id = None
        self._initialize_system()
        self._build_graph()
    
    def _initialize_system(self):
        """Inicializa o sistema com banco e agente padrão"""
        try:
            # Para inicialização síncrona, vamos usar load_existing_database_node de forma síncrona
            # ou criar uma versão síncrona temporária
            import os
            from sqlalchemy import create_engine

            # Verifica se banco existe
            if os.path.exists(SQL_DB_PATH):
                # Carrega banco existente
                self.engine = create_engine(f"sqlite:///{SQL_DB_PATH}")
                db = create_sql_database(self.engine)
                logging.info("Banco existente carregado")
            else:
                # Cria novo banco usando função síncrona temporária
                csv_path = get_active_csv_path()
                self.engine = self._create_engine_sync(csv_path)
                db = create_sql_database(self.engine)
                logging.info("Novo banco criado")

            # Armazena banco de dados
            self.db = db
            self.db_id = self.object_manager.store_database(db)

            # Cria agente SQL
            self.sql_agent = SQLAgentManager(db)

            # Armazena objetos no gerenciador
            self.agent_id = self.object_manager.store_sql_agent(self.sql_agent, self.db_id)
            self.engine_id = self.object_manager.store_engine(self.engine)
            self.cache_id = self.object_manager.store_cache_manager(self.cache_manager)

            logging.info("Sistema inicializado com sucesso")

        except Exception as e:
            logging.error(f"Erro ao inicializar sistema: {e}")
            raise

    def _create_engine_sync(self, csv_path: str):
        """Cria engine de forma síncrona para inicialização"""
        import pandas as pd
        from sqlalchemy import create_engine
        from sqlalchemy.types import DateTime, Integer, Float

        # Lê CSV
        df = pd.read_csv(csv_path, sep=';')

        # Processamento inteligente de tipos
        sql_types = {}
        df = self._smart_type_conversion(df, sql_types)

        # Cria engine e salva dados
        engine = create_engine(f"sqlite:///{SQL_DB_PATH}")
        df.to_sql("tabela", engine, index=False, if_exists="replace", dtype=sql_types)

        logging.info(f"Banco criado com {len(df)} registros")
        return engine
    
    def _build_graph(self):
        """Constrói o grafo LangGraph com nova arquitetura"""
        try:
            # Cria o StateGraph
            workflow = StateGraph(AgentState)

            # Adiciona nós de validação e preparação
            workflow.add_node("validate_input", validate_query_input_node)
            workflow.add_node("check_cache", check_cache_node)
            workflow.add_node("validate_processing", validate_processing_input_node)
            workflow.add_node("process_initial_context", process_initial_context_node)
            workflow.add_node("prepare_context", prepare_query_context_node)
            workflow.add_node("get_db_sample", get_database_sample_node)

            # Adiciona nós de processamento
            workflow.add_node("process_query", process_user_query_node)

            # Adiciona nós de gráficos
            workflow.add_node("graph_selection", graph_selection_node)
            workflow.add_node("graph_generation", graph_generation_node)

            # Adiciona nós de refinamento
            workflow.add_node("refine_response", refine_response_node)
            workflow.add_node("format_response", format_final_response_node)

            # Adiciona nós de cache e histórico
            workflow.add_node("cache_response", cache_response_node)
            workflow.add_node("update_history", update_history_node)

            # Define ponto de entrada
            workflow.set_entry_point("validate_input")

            # Fluxo principal
            workflow.add_edge("validate_input", "check_cache")

            # Condicional para cache hit ou processing
            workflow.add_conditional_edges(
                "check_cache",
                route_after_cache_check,
                {
                    "update_history": "update_history",
                    "validate_processing": "validate_processing",
                    "prepare_context": "prepare_context"
                }
            )

            # Fluxo do Processing Agent
            workflow.add_edge("validate_processing", "process_initial_context")
            workflow.add_edge("process_initial_context", "prepare_context")

            workflow.add_edge("prepare_context", "get_db_sample")
            workflow.add_edge("get_db_sample", "process_query")

            # Condicional para gráficos (após AgentSQL)
            workflow.add_conditional_edges(
                "process_query",
                should_generate_graph,
                {
                    "graph_selection": "graph_selection",
                    "refine_response": "refine_response",
                    "cache_response": "cache_response"
                }
            )

            # Fluxo dos gráficos
            workflow.add_edge("graph_selection", "graph_generation")

            # Após geração de gráfico, vai para refinamento ou cache
            workflow.add_conditional_edges(
                "graph_generation",
                should_refine_response,
                {
                    "refine_response": "refine_response",
                    "cache_response": "cache_response"
                }
            )

            workflow.add_edge("refine_response", "format_response")
            workflow.add_edge("format_response", "cache_response")
            workflow.add_edge("cache_response", "update_history")
            workflow.add_edge("update_history", END)

            # Compila o grafo
            memory = MemorySaver()
            self.app = workflow.compile(checkpointer=memory)

            logging.info("Grafo LangGraph construído com sucesso")

        except Exception as e:
            logging.error(f"Erro ao construir grafo: {e}")
            raise
    
    async def process_query(
        self,
        user_input: str,
        selected_model: str = "GPT-4o-mini",
        advanced_mode: bool = False,
        processing_enabled: bool = False,
        processing_model: str = "GPT-4o-mini",
        thread_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Processa uma query do usuário através do grafo

        Args:
            user_input: Entrada do usuário
            selected_model: Modelo LLM selecionado
            advanced_mode: Se deve usar refinamento avançado
            processing_enabled: Se deve usar o Processing Agent
            processing_model: Modelo para o Processing Agent
            thread_id: ID da thread para checkpoint

        Returns:
            Resultado do processamento
        """
        try:
            # Verifica se precisa recriar agente SQL com modelo diferente
            current_sql_agent = self.object_manager.get_sql_agent(self.agent_id)
            if current_sql_agent and current_sql_agent.model_name != selected_model:
                logging.info(f"Recriando agente SQL com modelo {selected_model}")

                # Recupera banco de dados associado ao agente
                db_id = self.object_manager.get_db_id_for_agent(self.agent_id)
                if db_id:
                    db = self.object_manager.get_database(db_id)
                    if db:
                        new_sql_agent = SQLAgentManager(db, selected_model)
                        self.agent_id = self.object_manager.store_sql_agent(new_sql_agent, db_id)
                        logging.info(f"Agente SQL recriado com sucesso para modelo {selected_model}")
                    else:
                        logging.error("Banco de dados não encontrado para recriar agente")
                else:
                    logging.error("ID do banco de dados não encontrado para o agente")

            # Log dos parâmetros recebidos
            logging.info(f"[MAIN GRAPH] ===== INICIANDO PROCESSAMENTO DE QUERY =====")
            logging.info(f"[MAIN GRAPH] User input: {user_input}")
            logging.info(f"[MAIN GRAPH] Selected model: {selected_model}")
            logging.info(f"[MAIN GRAPH] Advanced mode: {advanced_mode}")
            logging.info(f"[MAIN GRAPH] Processing enabled: {processing_enabled}")
            logging.info(f"[MAIN GRAPH] Processing model: {processing_model}")

            # Prepara estado inicial com IDs serializáveis
            initial_state = {
                "user_input": user_input,
                "selected_model": selected_model,
                "response": "",
                "advanced_mode": advanced_mode,
                "execution_time": 0.0,
                "error": None,
                "intermediate_steps": [],
                "db_sample_dict": {},
                # IDs para recuperar objetos não-serializáveis
                "agent_id": self.agent_id,
                "engine_id": self.engine_id,
                "db_id": self.db_id,
                "cache_id": self.cache_id,
                # Campos relacionados a gráficos
                "query_type": "sql_query",  # Será atualizado pela detecção
                "sql_query_extracted": None,
                "graph_type": None,
                "graph_data": None,
                "graph_image_id": None,
                "graph_generated": False,
                "graph_error": None,
                # Campos relacionados ao cache
                "cache_hit": False,
                # Campos relacionados ao Processing Agent
                "processing_enabled": processing_enabled,
                "processing_model": processing_model,
                "processing_agent_id": None,
                "suggested_query": None,
                "query_observations": None,
                "processing_result": None,
                "processing_success": False,
                "processing_error": None,
                # Campos relacionados ao refinamento
                "refined": False,
                "refinement_error": None,
                "refinement_quality": None,
                "quality_metrics": None,
                # Campos relacionados ao contexto SQL
                "sql_context": None,
                "sql_result": None
            }
            
            # Executa o grafo
            config = {"configurable": {"thread_id": thread_id}}
            result = await self.app.ainvoke(initial_state, config=config)
            
            logging.info(f"Query processada com sucesso: {user_input[:50]}...")
            return result
            
        except Exception as e:
            error_msg = f"Erro ao processar query: {e}"
            logging.error(error_msg)
            return {
                "user_input": user_input,
                "response": error_msg,
                "error": error_msg,
                "execution_time": 0.0
            }
    
    async def handle_csv_upload(self, file_path: str) -> Dict[str, Any]:
        """
        Processa upload de CSV usando nova arquitetura de nós

        Args:
            file_path: Caminho do arquivo CSV

        Returns:
            Resultado do upload
        """
        try:
            # Etapa 1: Processa CSV
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
                return csv_result

            # Etapa 2: Cria banco de dados
            db_state = csv_result.copy()
            db_result = await create_database_from_dataframe_node(db_state)

            if not db_result["success"]:
                return db_result

            # Etapa 3: Atualiza sistema
            if db_result["success"]:
                # Atualiza IDs dos objetos
                self.engine_id = db_result["engine_id"]
                self.db_id = db_result["db_id"]

                # Cria novo agente SQL
                new_engine = self.object_manager.get_engine(self.engine_id)
                new_db = self.object_manager.get_database(self.db_id)
                new_sql_agent = SQLAgentManager(new_db)

                # Atualiza agente
                self.agent_id = self.object_manager.store_sql_agent(new_sql_agent, self.db_id)

                # Limpa cache
                cache_manager = self.object_manager.get_cache_manager(self.cache_id)
                if cache_manager:
                    cache_manager.clear_cache()

                logging.info("[UPLOAD] Sistema atualizado com novo CSV")

            return db_result

        except Exception as e:
            error_msg = f"❌ Erro no upload de CSV: {e}"
            logging.error(error_msg)
            return {
                "success": False,
                "message": error_msg
            }
    
    async def reset_system(self) -> Dict[str, Any]:
        """
        Reseta o sistema ao estado inicial

        Returns:
            Resultado do reset
        """
        try:
            # Usa nó de reset customizado
            state = {
                "success": False,
                "message": "",
                "engine_id": self.engine_id,
                "agent_id": self.agent_id,
                "cache_id": self.cache_id
            }

            result = await self.custom_node_manager.execute_node("system_reset", state)

            # Se reset foi bem-sucedido, atualiza IDs
            if result.get("success"):
                self.engine_id = result.get("engine_id", self.engine_id)
                self.agent_id = result.get("agent_id", self.agent_id)
                # Cache ID permanece o mesmo, apenas é limpo

                logging.info("[RESET] Sistema resetado com sucesso")

            return result

        except Exception as e:
            error_msg = f"❌ Erro ao resetar sistema: {e}"
            logging.error(error_msg)
            return {
                "success": False,
                "message": error_msg
            }
    
    def toggle_advanced_mode(self, enabled: bool) -> str:
        """
        Alterna modo avançado
        
        Args:
            enabled: Se deve habilitar modo avançado
            
        Returns:
            Mensagem de status
        """
        message = "Modo avançado ativado." if enabled else "Modo avançado desativado."
        logging.info(f"[MODO AVANÇADO] {'Ativado' if enabled else 'Desativado'}")
        return message
    
    def get_history(self) -> list:
        """
        Retorna histórico de conversas
        
        Returns:
            Lista com histórico
        """
        return self.cache_manager.get_history()
    
    def clear_cache(self):
        """Limpa cache do sistema"""
        self.cache_manager.clear_cache()
        logging.info("Cache limpo")
    
    async def get_system_info(self) -> Dict[str, Any]:
        """
        Obtém informações do sistema
        
        Returns:
            Informações do sistema
        """
        state = {
            "engine": self.engine,
            "sql_agent": self.sql_agent,
            "cache_manager": self.cache_manager
        }
        
        result = await self.custom_node_manager.execute_node("system_info", state)
        return result.get("system_info", {})
    
    async def validate_system(self) -> Dict[str, Any]:
        """
        Valida o estado do sistema
        
        Returns:
            Resultado da validação
        """
        state = {
            "engine": self.engine,
            "sql_agent": self.sql_agent,
            "cache_manager": self.cache_manager
        }
        
        result = await self.custom_node_manager.execute_node("system_validation", state)
        return result.get("validation", {})

    def _smart_type_conversion(self, df, sql_types):
        """
        Conversão inteligente de tipos de dados com suporte a formatos brasileiros
        """
        import re

        logging.info("[TYPE_CONVERSION] 🔧 Iniciando conversão inteligente de tipos")

        for col in df.columns:
            col_data = df[col].dropna()  # Remove NaN para análise

            if len(col_data) == 0:
                continue

            # Amostra para análise (primeiros 100 valores não-nulos)
            sample = col_data.head(100).astype(str)

            logging.debug(f"[TYPE_CONVERSION] 📊 Analisando coluna: {col}")

            # 1. DETECTAR DATAS
            if self._is_date_column(sample):
                try:
                    df[col] = self._convert_to_date(df[col])
                    sql_types[col] = DateTime
                    logging.debug(f"[TYPE_CONVERSION] ✅ {col} → DATETIME")
                    continue
                except Exception as e:
                    logging.warning(f"[TYPE_CONVERSION] ⚠️ Falha ao converter {col} para data: {e}")

            # 2. DETECTAR NÚMEROS INTEIROS (PRIORIDADE ALTA)
            if self._is_integer_column(sample):
                try:
                    # Converter removendo caracteres não numéricos, mas mantendo negativos
                    def clean_integer(value):
                        if pd.isna(value):
                            return None
                        value_str = str(value).strip()
                        # Manter apenas dígitos e sinal negativo
                        clean_value = ''.join(c for c in value_str if c.isdigit() or c == '-')
                        if clean_value and clean_value != '-':
                            return int(clean_value)
                        return None

                    df[col] = df[col].apply(clean_integer).astype('Int64')
                    sql_types[col] = Integer
                    logging.debug(f"[TYPE_CONVERSION] ✅ {col} → INTEGER")
                    continue
                except Exception as e:
                    logging.warning(f"[TYPE_CONVERSION] ⚠️ Falha ao converter {col} para inteiro: {e}")

            # 3. DETECTAR VALORES MONETÁRIOS
            if self._is_monetary_column(sample):
                try:
                    df[col] = self._convert_to_monetary(df[col])
                    sql_types[col] = Float
                    logging.debug(f"[TYPE_CONVERSION] ✅ {col} → FLOAT (monetário)")
                    continue
                except Exception as e:
                    logging.warning(f"[TYPE_CONVERSION] ⚠️ Falha ao converter {col} para monetário: {e}")

            # 4. DETECTAR NÚMEROS DECIMAIS
            if self._is_float_column(sample):
                try:
                    df[col] = self._convert_to_float(df[col])
                    sql_types[col] = Float
                    logging.debug(f"[TYPE_CONVERSION] ✅ {col} → FLOAT")
                    continue
                except Exception as e:
                    logging.warning(f"[TYPE_CONVERSION] ⚠️ Falha ao converter {col} para float: {e}")

            # 5. MANTER COMO TEXTO (padrão)
            logging.debug(f"[TYPE_CONVERSION] 📝 {col} → TEXT (padrão)")

        # Resumo da conversão
        type_summary = {}
        for col, sql_type in sql_types.items():
            type_name = sql_type.__name__ if hasattr(sql_type, '__name__') else str(sql_type).split('.')[-1].replace('>', '')
            if type_name not in type_summary:
                type_summary[type_name] = 0
            type_summary[type_name] += 1

        summary_text = ", ".join([f"{count} {type_name}" for type_name, count in type_summary.items()])
        logging.info(f"[TYPE_CONVERSION] ✅ Conversão concluída: {summary_text}")
        return df

    def _is_date_column(self, sample):
        """Detecta se uma coluna contém datas BASEADO APENAS NOS VALORES"""
        import re

        # Padrões de data brasileiros e internacionais
        date_patterns = [
            r'^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4}$',  # DD/MM/YYYY ou DD-MM-YYYY
            r'^\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}$',  # YYYY/MM/DD ou YYYY-MM-DD
            r'^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2}$',  # DD/MM/YY
        ]

        # Verificar se pelo menos 70% dos valores seguem padrão de data
        date_count = 0
        for value in sample:
            if pd.isna(value) or value == '':
                continue
            for pattern in date_patterns:
                if re.match(pattern, str(value).strip()):
                    date_count += 1
                    break

        return date_count / len(sample) >= 0.7

    def _is_monetary_column(self, sample):
        """Detecta se uma coluna contém valores monetários BASEADO APENAS NOS VALORES"""
        import re

        # Padrões monetários brasileiros e internacionais
        money_patterns = [
            r'^R\$\s*\d+[,\.]\d{2}$',  # R$ 10,50 ou R$ 10.50
            r'^\d+[,\.]\d{2}$',        # 10,50 ou 10.50
            r'^R\$\s*\d+$',            # R$ 10
            r'^\$\s*\d+[,\.]\d{2}$',   # $ 10.50
            r'^\$\s*\d+$',             # $ 10
        ]

        # Verificar se pelo menos 60% dos valores seguem padrão monetário
        money_count = 0
        for value in sample:
            if pd.isna(value) or value == '':
                continue
            value_str = str(value).strip()
            for pattern in money_patterns:
                if re.match(pattern, value_str):
                    money_count += 1
                    break

        return money_count / len(sample) >= 0.6

    def _is_integer_column(self, sample):
        """Detecta se uma coluna contém números inteiros"""
        try:
            # Primeiro, verificar se há vírgulas ou pontos decimais nos valores
            has_decimal_separators = False
            valid_numeric_count = 0
            integer_count = 0

            for value in sample:
                if pd.isna(value) or value == '':
                    continue

                value_str = str(value).strip()

                # Se contém vírgula ou ponto seguido de dígitos, é decimal
                if (',' in value_str and any(c.isdigit() for c in value_str.split(',')[-1])) or \
                   ('.' in value_str and any(c.isdigit() for c in value_str.split('.')[-1])):
                    has_decimal_separators = True
                    break

                # Tentar converter para número
                try:
                    # Remover espaços e caracteres não numéricos (exceto - para negativos)
                    clean_value = ''.join(c for c in value_str if c.isdigit() or c == '-')
                    if clean_value and clean_value != '-':
                        num_value = int(clean_value)
                        valid_numeric_count += 1
                        integer_count += 1
                except:
                    # Se não conseguir converter para int, tentar float
                    try:
                        float_value = float(value_str)
                        valid_numeric_count += 1
                        # Se o float é igual ao int, conta como inteiro
                        if float_value == int(float_value):
                            integer_count += 1
                    except:
                        continue

            # Se encontrou separadores decimais, não é coluna de inteiros
            if has_decimal_separators:
                return False

            # Verificar se pelo menos 80% são números válidos
            if valid_numeric_count == 0 or valid_numeric_count / len(sample) < 0.8:
                return False

            # Verificar se pelo menos 95% dos números válidos são inteiros
            return integer_count / valid_numeric_count >= 0.95

        except Exception as e:
            logging.debug(f"Erro na detecção de inteiros: {e}")
            return False

    def _is_float_column(self, sample):
        """Detecta se uma coluna contém números decimais (com vírgula ou ponto)"""
        try:
            has_decimal_values = False
            valid_numeric_count = 0

            for value in sample:
                if pd.isna(value) or value == '':
                    continue

                value_str = str(value).strip()

                # Verificar se contém separadores decimais com dígitos após
                if (',' in value_str and any(c.isdigit() for c in value_str.split(',')[-1])) or \
                   ('.' in value_str and any(c.isdigit() for c in value_str.split('.')[-1])):
                    has_decimal_values = True

                # Tentar converter para numérico (substituindo vírgula por ponto)
                try:
                    clean_value = value_str.replace(',', '.')
                    float(clean_value)
                    valid_numeric_count += 1
                except:
                    continue

            # Só é float se tem separadores decimais E pelo menos 80% são números válidos
            if not has_decimal_values:
                return False

            return valid_numeric_count / len(sample) >= 0.8

        except Exception as e:
            logging.debug(f"Erro na detecção de floats: {e}")
            return False

    def _convert_to_date(self, series):
        """Converte série para datetime com formatos brasileiros"""
        # Tentar diferentes formatos de data
        date_formats = [
            '%d/%m/%Y',    # 31/12/2023
            '%d-%m-%Y',    # 31-12-2023
            '%d.%m.%Y',    # 31.12.2023
            '%Y-%m-%d',    # 2023-12-31
            '%Y/%m/%d',    # 2023/12/31
            '%d/%m/%y',    # 31/12/23
        ]

        for fmt in date_formats:
            try:
                return pd.to_datetime(series, format=fmt, errors='raise')
            except:
                continue

        # Se nenhum formato específico funcionou, usar inferência automática
        try:
            return pd.to_datetime(series, dayfirst=True, errors='coerce')
        except:
            raise ValueError("Não foi possível converter para data")

    def _convert_to_monetary(self, series):
        """Converte série para valores monetários (float)"""
        def clean_monetary(value):
            if pd.isna(value):
                return None

            # Converter para string e limpar
            value_str = str(value).strip()

            # Remover símbolos monetários
            value_str = value_str.replace('R$', '').replace('$', '').strip()

            # Tratar formato brasileiro (vírgula como decimal)
            if ',' in value_str and '.' in value_str:
                # Formato: 1.234,56 → 1234.56
                value_str = value_str.replace('.', '').replace(',', '.')
            elif ',' in value_str:
                # Formato: 1234,56 → 1234.56
                value_str = value_str.replace(',', '.')

            try:
                return float(value_str)
            except:
                return None

        return series.apply(clean_monetary)

    def _convert_to_float(self, series):
        """Converte série para float com formato brasileiro"""
        def clean_float(value):
            if pd.isna(value):
                return None

            value_str = str(value).strip()

            # Tratar formato brasileiro
            if ',' in value_str:
                value_str = value_str.replace(',', '.')

            try:
                return float(value_str)
            except:
                return None

        return series.apply(clean_float)

# Instância global do gerenciador
_graph_manager: Optional[AgentGraphManager] = None

def get_graph_manager() -> AgentGraphManager:
    """
    Retorna instância singleton do gerenciador de grafo
    
    Returns:
        AgentGraphManager
    """
    global _graph_manager
    if _graph_manager is None:
        _graph_manager = AgentGraphManager()
    return _graph_manager

async def initialize_graph() -> AgentGraphManager:
    """
    Inicializa o grafo principal
    
    Returns:
        AgentGraphManager inicializado
    """
    try:
        manager = get_graph_manager()
        
        # Valida sistema
        validation = await manager.validate_system()
        if not validation.get("overall_valid", False):
            logging.warning("Sistema não passou na validação completa")
        
        logging.info("Grafo principal inicializado e validado")
        return manager
        
    except Exception as e:
        logging.error(f"Erro ao inicializar grafo: {e}")
        raise

# Classe GraphManager removida - funcionalidade movida para AgentGraphManager
