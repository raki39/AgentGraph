"""
Nó para operações de banco de dados
"""
import os
import logging
import pandas as pd
from typing import Dict, Any, TypedDict, Optional
from sqlalchemy import create_engine

from utils.config import SQL_DB_PATH
from utils.database import create_sql_database, validate_database
from utils.object_manager import get_object_manager

class DatabaseState(TypedDict):
    """Estado para operações de banco de dados"""
    success: bool
    message: str
    database_info: dict
    engine_id: str
    db_id: str

async def create_database_from_dataframe_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nó para criar banco de dados a partir de DataFrame processado
    
    Args:
        state: Estado contendo informações do DataFrame processado
        
    Returns:
        Estado atualizado com informações do banco
    """
    try:
        obj_manager = get_object_manager()
        
        # Recupera DataFrame processado
        df_id = state.get("dataframe_id")
        if not df_id:
            raise ValueError("ID do DataFrame não encontrado no estado")
        
        processed_df = obj_manager.get_object(df_id)
        if processed_df is None:
            raise ValueError("DataFrame processado não encontrado")
        
        # Recupera informações das colunas
        column_info = state.get("column_info", {})
        sql_types = column_info.get("sql_types", {})
        
        # Cria engine do banco
        engine = create_engine(f"sqlite:///{SQL_DB_PATH}")
        
        # Salva DataFrame no banco
        processed_df.to_sql(
            "tabela", 
            engine, 
            index=False, 
            if_exists="replace", 
            dtype=sql_types
        )
        
        logging.info(f"[DATABASE] Banco criado com {len(processed_df)} registros")
        
        # Cria objeto SQLDatabase do LangChain
        db = create_sql_database(engine)
        
        # Valida banco
        is_valid = validate_database(engine)
        
        # Armazena objetos no gerenciador
        engine_id = obj_manager.store_engine(engine)
        db_id = obj_manager.store_database(db)
        
        # Informações do banco
        database_info = {
            "path": SQL_DB_PATH,
            "table_name": "tabela",
            "total_records": len(processed_df),
            "columns": list(processed_df.columns),
            "column_types": {col: str(dtype) for col, dtype in processed_df.dtypes.items()},
            "is_valid": is_valid,
            "sql_types_used": {col: str(sql_type) for col, sql_type in sql_types.items()}
        }
        
        # Atualiza estado
        state.update({
            "success": True,
            "message": f"✅ Banco de dados criado com sucesso! {len(processed_df)} registros salvos",
            "database_info": database_info,
            "engine_id": engine_id,
            "db_id": db_id
        })
        
        logging.info(f"[DATABASE] Banco criado e validado: {database_info}")
        
    except Exception as e:
        error_msg = f"❌ Erro ao criar banco de dados: {e}"
        logging.error(f"[DATABASE] {error_msg}")
        state.update({
            "success": False,
            "message": error_msg,
            "database_info": {},
            "engine_id": "",
            "db_id": ""
        })
    
    return state

async def load_existing_database_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nó para carregar banco de dados existente
    
    Args:
        state: Estado atual
        
    Returns:
        Estado atualizado com informações do banco existente
    """
    try:
        if not os.path.exists(SQL_DB_PATH):
            raise ValueError("Banco de dados não encontrado")
        
        # Cria engine
        engine = create_engine(f"sqlite:///{SQL_DB_PATH}")
        
        # Cria objeto SQLDatabase
        db = create_sql_database(engine)
        
        # Valida banco
        is_valid = validate_database(engine)
        
        # Obtém informações do banco
        try:
            sample_df = pd.read_sql_query("SELECT * FROM tabela LIMIT 5", engine)
            total_records_df = pd.read_sql_query("SELECT COUNT(*) as count FROM tabela", engine)
            total_records = total_records_df.iloc[0]['count']
            
            database_info = {
                "path": SQL_DB_PATH,
                "table_name": "tabela",
                "total_records": total_records,
                "columns": list(sample_df.columns),
                "column_types": {col: str(dtype) for col, dtype in sample_df.dtypes.items()},
                "is_valid": is_valid,
                "sample_data": sample_df.head(3).to_dict()
            }
        except Exception as e:
            logging.warning(f"Erro ao obter informações detalhadas do banco: {e}")
            database_info = {
                "path": SQL_DB_PATH,
                "table_name": "tabela",
                "is_valid": is_valid,
                "error": str(e)
            }
        
        # Armazena objetos no gerenciador
        obj_manager = get_object_manager()
        engine_id = obj_manager.store_engine(engine)
        db_id = obj_manager.store_database(db)
        
        # Atualiza estado
        state.update({
            "success": True,
            "message": "✅ Banco de dados existente carregado com sucesso",
            "database_info": database_info,
            "engine_id": engine_id,
            "db_id": db_id
        })
        
        logging.info(f"[DATABASE] Banco existente carregado: {database_info}")
        
    except Exception as e:
        error_msg = f"❌ Erro ao carregar banco existente: {e}"
        logging.error(f"[DATABASE] {error_msg}")
        state.update({
            "success": False,
            "message": error_msg,
            "database_info": {},
            "engine_id": "",
            "db_id": ""
        })
    
    return state

async def get_database_sample_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nó para obter amostra dos dados do banco
    
    Args:
        state: Estado contendo ID da engine
        
    Returns:
        Estado atualizado com amostra dos dados
    """
    try:
        obj_manager = get_object_manager()
        
        # Recupera engine
        engine_id = state.get("engine_id")
        if not engine_id:
            raise ValueError("ID da engine não encontrado")
        
        engine = obj_manager.get_engine(engine_id)
        if not engine:
            raise ValueError("Engine não encontrada")
        
        # Determina qual tabela usar para amostra
        connection_type = state.get("connection_type", "csv")

        if connection_type == "postgresql":
            # Para PostgreSQL, sempre usa uma tabela com dados para amostra
            # Independente do modo, a amostra é só para contexto
            table_name = "users"  # Tabela que sabemos que tem dados
            logging.info(f"[DATABASE] PostgreSQL - usando tabela 'users' para amostra")
        else:
            table_name = "tabela"  # Padrão para CSV
            logging.info(f"[DATABASE] CSV - usando tabela padrão: {table_name}")

        # Obtém amostra dos dados
        sample_df = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 10", engine)
        
        # Converte para formato serializável
        db_sample_dict = {
            "data": sample_df.to_dict('records'),
            "columns": list(sample_df.columns),
            "dtypes": sample_df.dtypes.astype(str).to_dict(),
            "shape": sample_df.shape
        }
        
        state["db_sample_dict"] = db_sample_dict
        
        logging.info(f"[DATABASE] Amostra obtida: {sample_df.shape[0]} registros")
        
    except Exception as e:
        error_msg = f"Erro ao obter amostra do banco: {e}"
        logging.error(f"[DATABASE] {error_msg}")
        state["db_sample_dict"] = {}
        state["error"] = error_msg
    
    return state
