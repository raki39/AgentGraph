"""
Sistema de limpeza automática para sessões temporárias
Jobs periódicos para limpar sessões expiradas, diretórios órfãos e cache antigo
"""
import logging
import time
import threading
from typing import Dict, Any
from datetime import datetime, timedelta

from utils.session_manager import get_session_manager
from utils.session_paths import get_session_paths

class SessionCleanupService:
    """
    Serviço de limpeza automática de sessões
    Executa jobs periódicos para manter o sistema limpo
    """
    
    def __init__(self):
        self.session_manager = get_session_manager()
        self.session_paths = get_session_paths()
        self.cleanup_interval = 300  # 5 minutos
        self.running = False
        self.cleanup_thread = None
        
    def start_cleanup_service(self):
        """Inicia o serviço de limpeza em background"""
        if self.running:
            logging.warning("[SESSION_CLEANUP] Serviço já está rodando")
            return
        
        self.running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        logging.info(f"[SESSION_CLEANUP] Serviço iniciado (intervalo: {self.cleanup_interval}s)")
    
    def stop_cleanup_service(self):
        """Para o serviço de limpeza"""
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        
        logging.info("[SESSION_CLEANUP] Serviço parado")
    
    def _cleanup_loop(self):
        """Loop principal de limpeza"""
        while self.running:
            try:
                self.run_cleanup()
                time.sleep(self.cleanup_interval)
            except Exception as e:
                logging.error(f"[SESSION_CLEANUP] Erro no loop de limpeza: {e}")
                time.sleep(60)  # Aguarda 1 minuto em caso de erro
    
    def run_cleanup(self) -> Dict[str, int]:
        """
        Executa limpeza completa
        
        Returns:
            Estatísticas da limpeza
        """
        start_time = time.time()
        stats = {
            "sessions_removed": 0,
            "directories_removed": 0,
            "cache_cleared": 0,
            "errors": 0
        }
        
        try:
            logging.info("[SESSION_CLEANUP] Iniciando limpeza automática...")
            
            # 1. Limpar sessões expiradas do Redis
            try:
                removed_sessions = self.session_manager.cleanup_expired_sessions()
                stats["sessions_removed"] = removed_sessions
            except Exception as e:
                logging.error(f"[SESSION_CLEANUP] Erro ao limpar sessões: {e}")
                stats["errors"] += 1
            
            # 2. Limpar diretórios órfãos
            try:
                removed_dirs = self._cleanup_orphaned_directories()
                stats["directories_removed"] = removed_dirs
            except Exception as e:
                logging.error(f"[SESSION_CLEANUP] Erro ao limpar diretórios: {e}")
                stats["errors"] += 1
            
            # 3. Limpar cache do Celery (se disponível)
            try:
                cache_cleared = self._cleanup_celery_cache()
                stats["cache_cleared"] = cache_cleared
            except Exception as e:
                logging.error(f"[SESSION_CLEANUP] Erro ao limpar cache: {e}")
                stats["errors"] += 1
            
            execution_time = time.time() - start_time
            
            if any(stats.values()):
                logging.info(f"[SESSION_CLEANUP] Limpeza concluída em {execution_time:.2f}s: {stats}")
            
            return stats
            
        except Exception as e:
            logging.error(f"[SESSION_CLEANUP] Erro geral na limpeza: {e}")
            stats["errors"] += 1
            return stats
    
    def _cleanup_orphaned_directories(self) -> int:
        """
        Remove diretórios de sessões que não existem mais no Redis
        
        Returns:
            Número de diretórios removidos
        """
        import os
        import shutil
        
        removed_count = 0
        
        try:
            sessions_dir = self.session_manager.sessions_base_dir
            if not os.path.exists(sessions_dir):
                return 0
            
            # Lista todos os diretórios de sessão
            for item in os.listdir(sessions_dir):
                item_path = os.path.join(sessions_dir, item)
                
                if os.path.isdir(item_path):
                    # Verifica se sessão ainda existe no Redis
                    session_data = self.session_manager.get_session(item)
                    
                    if not session_data:
                        # Sessão não existe mais, remove diretório
                        try:
                            # Windows: força remoção com retry
                            self._force_remove_directory(item_path)
                            logging.info(f"[SESSION_CLEANUP] Diretório órfão removido: {item}")
                            removed_count += 1
                        except Exception as e:
                            logging.error(f"[SESSION_CLEANUP] Erro ao remover diretório {item}: {e}")
            
            return removed_count
            
        except Exception as e:
            logging.error(f"[SESSION_CLEANUP] Erro ao limpar diretórios órfãos: {e}")
            return 0

    def _force_remove_directory(self, directory_path: str):
        """
        Remove diretório com retry para Windows

        Args:
            directory_path: Caminho do diretório
        """
        import time
        import stat

        def handle_remove_readonly(func, path, exc):
            """Handler para arquivos readonly no Windows"""
            if os.path.exists(path):
                os.chmod(path, stat.S_IWRITE)
                func(path)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                shutil.rmtree(directory_path, onerror=handle_remove_readonly)
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    logging.warning(f"[SESSION_CLEANUP] Tentativa {attempt + 1} falhou: {e}, tentando novamente...")
                    time.sleep(0.5)
                else:
                    raise

    def _cleanup_celery_cache(self) -> int:
        """
        Limpa cache do Celery para sessões expiradas
        
        Returns:
            Número de entradas de cache removidas
        """
        try:
            # Importa aqui para evitar dependência circular
            from tasks import cleanup_session_cache, get_cache_stats
            
            cache_stats = get_cache_stats()
            removed_count = 0
            
            # Para cada sessão no cache, verifica se ainda existe
            for session_id in list(cache_stats.get("sessions", {}).keys()):
                session_data = self.session_manager.get_session(session_id)
                
                if not session_data:
                    # Sessão expirou, remove do cache
                    if cleanup_session_cache(session_id):
                        removed_count += 1
                        logging.info(f"[SESSION_CLEANUP] Cache removido para sessão: {session_id}")
            
            return removed_count
            
        except Exception as e:
            logging.error(f"[SESSION_CLEANUP] Erro ao limpar cache do Celery: {e}")
            return 0
    
    def force_cleanup_session(self, session_id: str) -> bool:
        """
        Força limpeza de uma sessão específica
        
        Args:
            session_id: ID da sessão
            
        Returns:
            True se limpeza foi bem-sucedida
        """
        try:
            logging.info(f"[SESSION_CLEANUP] Forçando limpeza da sessão: {session_id}")
            
            # Remove do Redis
            self.session_manager.delete_session(session_id)
            
            # Remove diretório
            self.session_paths.cleanup_session_directory(session_id)
            
            # Remove cache do Celery
            try:
                from tasks import cleanup_session_cache
                cleanup_session_cache(session_id)
            except:
                pass  # Não é crítico se falhar
            
            logging.info(f"[SESSION_CLEANUP] Sessão {session_id} limpa com sucesso")
            return True
            
        except Exception as e:
            logging.error(f"[SESSION_CLEANUP] Erro ao limpar sessão {session_id}: {e}")
            return False
    
    def get_cleanup_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do serviço de limpeza
        
        Returns:
            Dicionário com estatísticas
        """
        try:
            session_stats = self.session_manager.get_session_stats()
            
            return {
                "service_running": self.running,
                "cleanup_interval_seconds": self.cleanup_interval,
                "session_stats": session_stats,
                "last_cleanup": datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"[SESSION_CLEANUP] Erro ao obter estatísticas: {e}")
            return {}

# Instância global do serviço
_cleanup_service = None

def get_cleanup_service() -> SessionCleanupService:
    """Retorna instância singleton do serviço de limpeza"""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = SessionCleanupService()
    return _cleanup_service

def start_cleanup_service():
    """Inicia o serviço de limpeza automática"""
    service = get_cleanup_service()
    service.start_cleanup_service()

def stop_cleanup_service():
    """Para o serviço de limpeza automática"""
    global _cleanup_service
    if _cleanup_service:
        _cleanup_service.stop_cleanup_service()

def run_manual_cleanup() -> Dict[str, int]:
    """Executa limpeza manual"""
    service = get_cleanup_service()
    return service.run_cleanup()
