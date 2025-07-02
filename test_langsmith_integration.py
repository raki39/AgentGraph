"""
Teste da integração LangSmith com AgentGraph
"""
import asyncio
import logging
import os
from utils.config import (
    is_langsmith_enabled, 
    get_langsmith_metadata,
    LANGSMITH_PROJECT,
    LANGSMITH_API_KEY,
    LANGSMITH_TRACING
)

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_langsmith_configuration():
    """Testa se as configurações do LangSmith estão corretas"""
    print("\n=== Teste de Configuração LangSmith ===")
    
    print(f"LANGSMITH_API_KEY: {'✅ Configurada' if LANGSMITH_API_KEY else '❌ Não configurada'}")
    print(f"LANGSMITH_TRACING: {LANGSMITH_TRACING}")
    print(f"LANGSMITH_PROJECT: {LANGSMITH_PROJECT}")
    print(f"LangSmith Habilitado: {'✅ Sim' if is_langsmith_enabled() else '❌ Não'}")
    
    if is_langsmith_enabled():
        metadata = get_langsmith_metadata()
        print(f"Metadados: {metadata}")
        return True
    else:
        print("⚠️ LangSmith não está habilitado. Configure LANGSMITH_API_KEY e LANGSMITH_TRACING=true")
        return False

def test_environment_variables():
    """Testa se as variáveis de ambiente estão definidas"""
    print("\n=== Teste de Variáveis de Ambiente ===")
    
    env_vars = [
        "LANGSMITH_API_KEY",
        "LANGSMITH_TRACING", 
        "LANGSMITH_ENDPOINT",
        "LANGSMITH_PROJECT"
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        status = "✅ Definida" if value else "❌ Não definida"
        print(f"{var}: {status}")
        if value and var != "LANGSMITH_API_KEY":  # Não mostrar API key completa
            print(f"  Valor: {value}")

async def test_simple_langchain_trace():
    """Testa um trace simples com LangChain"""
    print("\n=== Teste de Trace Simples ===")
    
    if not is_langsmith_enabled():
        print("❌ LangSmith não habilitado, pulando teste de trace")
        return False
    
    try:
        # Importa apenas se LangSmith estiver habilitado
        from langchain_openai import ChatOpenAI
        from utils.config import OPENAI_API_KEY
        
        if not OPENAI_API_KEY:
            print("❌ OPENAI_API_KEY não configurada, pulando teste")
            return False
        
        print("🔍 Enviando trace de teste para LangSmith...")
        
        # Cria modelo com configuração mínima
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=50
        )
        
        # Executa uma chamada simples que será rastreada
        response = llm.invoke("Diga apenas 'Teste LangSmith funcionando'")
        
        print(f"✅ Resposta recebida: {response.content}")
        print(f"🎯 Trace enviado para projeto: {LANGSMITH_PROJECT}")
        print("📊 Verifique o dashboard LangSmith para ver o trace")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de trace: {e}")
        return False

async def test_agentgraph_integration():
    """Testa integração com o sistema AgentGraph"""
    print("\n=== Teste de Integração AgentGraph ===")
    
    try:
        from graphs.main_graph import get_graph_manager
        
        print("🔍 Testando inicialização do grafo...")
        
        # Obtém o gerenciador do grafo
        graph_manager = get_graph_manager()
        
        if graph_manager:
            print("✅ Graph manager inicializado")
            
            # Testa uma query simples se LangSmith estiver habilitado
            if is_langsmith_enabled():
                print("🔍 Testando query com LangSmith...")
                
                # Query de teste simples
                test_query = "Olá"
                result = await graph_manager.process_query(
                    user_input=test_query,
                    selected_model="GPT-4o-mini",
                    advanced_mode=False
                )
                
                print(f"✅ Query processada: {result.get('response', 'Sem resposta')[:100]}...")
                print(f"🎯 Trace completo enviado para: {LANGSMITH_PROJECT}")
                
            return True
        else:
            print("❌ Falha ao inicializar graph manager")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste de integração: {e}")
        return False

async def main():
    """Função principal de teste"""
    print("🚀 Iniciando testes de integração LangSmith")
    print("=" * 50)
    
    # Teste 1: Configuração
    config_ok = test_langsmith_configuration()
    
    # Teste 2: Variáveis de ambiente
    test_environment_variables()
    
    # Teste 3: Trace simples (apenas se configurado)
    if config_ok:
        await test_simple_langchain_trace()
        
        # Teste 4: Integração completa
        await test_agentgraph_integration()
    
    print("\n" + "=" * 50)
    print("🏁 Testes concluídos!")
    
    if config_ok:
        print("✅ LangSmith está configurado e funcionando")
        print(f"📊 Acesse: https://smith.langchain.com/projects/{LANGSMITH_PROJECT}")
    else:
        print("ℹ️ Para habilitar LangSmith:")
        print("1. Configure LANGSMITH_API_KEY no .env")
        print("2. Configure LANGSMITH_TRACING=true")
        print("3. Execute novamente este teste")

if __name__ == "__main__":
    asyncio.run(main())
