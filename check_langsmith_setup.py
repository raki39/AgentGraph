#!/usr/bin/env python3
"""
Script de verificação rápida da configuração LangSmith
"""
import os
import sys
from pathlib import Path

def check_env_file():
    """Verifica se arquivo .env existe"""
    env_file = Path(".env")
    if env_file.exists():
        print("✅ Arquivo .env encontrado")
        return True
    else:
        print("❌ Arquivo .env não encontrado")
        print("💡 Copie .env.example para .env e configure as variáveis")
        return False

def check_langsmith_vars():
    """Verifica variáveis do LangSmith"""
    print("\n🔍 Verificando configuração LangSmith:")
    
    vars_to_check = {
        "LANGSMITH_API_KEY": "API Key do LangSmith",
        "LANGSMITH_TRACING": "Habilitação do tracing", 
        "LANGSMITH_PROJECT": "Nome do projeto",
        "LANGSMITH_ENDPOINT": "Endpoint da API"
    }
    
    all_configured = True
    
    for var, description in vars_to_check.items():
        value = os.getenv(var)
        if value:
            if var == "LANGSMITH_API_KEY":
                # Mostra apenas parte da API key
                display_value = f"{value[:10]}...{value[-4:]}" if len(value) > 14 else "***"
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
        else:
            print(f"❌ {var}: Não configurada ({description})")
            all_configured = False
    
    return all_configured

def check_dependencies():
    """Verifica se dependências estão instaladas"""
    print("\n📦 Verificando dependências:")
    
    required_packages = [
        "langsmith",
        "langchain", 
        "langgraph",
        "langchain_openai",
        "langchain_anthropic"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}: Instalado")
        except ImportError:
            print(f"❌ {package}: Não instalado")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n💡 Para instalar dependências faltantes:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_config_module():
    """Verifica se módulo de configuração funciona"""
    print("\n⚙️ Verificando módulo de configuração:")
    
    try:
        from utils.config import (
            is_langsmith_enabled,
            get_langsmith_metadata,
            LANGSMITH_PROJECT
        )
        print("✅ Módulo utils.config importado com sucesso")
        
        enabled = is_langsmith_enabled()
        print(f"✅ LangSmith habilitado: {enabled}")
        
        if enabled:
            metadata = get_langsmith_metadata()
            print(f"✅ Metadados: {metadata}")
            print(f"✅ Projeto: {LANGSMITH_PROJECT}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao importar configuração: {e}")
        return False

def main():
    """Função principal"""
    print("🚀 Verificação da Configuração LangSmith - AgentGraph")
    print("=" * 60)
    
    # Carrega variáveis de ambiente se .env existir
    env_exists = check_env_file()
    if env_exists:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            print("✅ Variáveis de ambiente carregadas do .env")
        except ImportError:
            print("⚠️ python-dotenv não instalado, usando variáveis do sistema")
    
    # Verificações
    checks = [
        ("Dependências", check_dependencies),
        ("Variáveis LangSmith", check_langsmith_vars),
        ("Módulo de Configuração", check_config_module)
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n{'='*20} {name} {'='*20}")
        result = check_func()
        results.append((name, result))
    
    # Resumo final
    print("\n" + "="*60)
    print("📊 RESUMO DA VERIFICAÇÃO")
    print("="*60)
    
    all_ok = True
    for name, result in results:
        status = "✅ OK" if result else "❌ FALHA"
        print(f"{name}: {status}")
        if not result:
            all_ok = False
    
    print("\n" + "="*60)
    if all_ok:
        print("🎉 TUDO CONFIGURADO CORRETAMENTE!")
        print("🚀 Você pode executar: python app.py")
        print("📊 Traces aparecerão em: https://smith.langchain.com/")
    else:
        print("⚠️ CONFIGURAÇÃO INCOMPLETA")
        print("📝 Siga as instruções acima para corrigir os problemas")
        print("📖 Consulte: LANGSMITH_INTEGRATION.md para mais detalhes")
    
    print("="*60)

if __name__ == "__main__":
    main()
