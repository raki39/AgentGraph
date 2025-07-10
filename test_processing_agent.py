"""
Teste básico do Processing Agent
"""
import asyncio
import pandas as pd
import logging
from agents.processing_agent import ProcessingAgentManager
from agents.tools import prepare_processing_context

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_processing_agent():
    """Teste básico do Processing Agent"""

    print("="*60)
    print("TESTE DO PROCESSING AGENT")
    print("="*60)

    # Dados de exemplo
    data = {
        'PRODUTO': ['Produto A', 'Produto B', 'Produto C'],
        'PRECO': [10.50, 25.30, 15.75],
        'CATEGORIA': ['Categoria 1', 'Categoria 2', 'Categoria 1'],
        'ESTOQUE': [100, 50, 75]
    }
    df_sample = pd.DataFrame(data)

    print(f"Dados de exemplo:")
    print(df_sample)
    print("\n" + "-"*50 + "\n")

    # Pergunta de teste
    user_query = "Qual é o produto mais caro e quantos temos em estoque?"
    print(f"Pergunta: {user_query}")
    print("\n" + "-"*50 + "\n")

    # Prepara contexto
    context = prepare_processing_context(user_query, df_sample)
    print("Contexto preparado:")
    print(context)
    print("\n" + "="*50 + "\n")

    # Cria Processing Agent
    print("Criando Processing Agent...")
    processing_agent = ProcessingAgentManager("gpt-4o-mini")

    # Processa contexto
    print("Processando contexto...")
    result = await processing_agent.process_context(context)

    print("\n" + "="*50)
    print("RESULTADO DO PROCESSING AGENT:")
    print("="*50)
    print(f"Sucesso: {result['success']}")
    print(f"Modelo usado: {result['model_used']}")
    print(f"Pergunta processada: {result['processed_question']}")
    print(f"Query sugerida: {result['suggested_query']}")
    print("\nResposta completa:")
    print(result['output'])
    print("="*50)

async def test_processing_flow():
    """Teste do fluxo completo com diferentes modelos"""

    print("\n" + "="*60)
    print("TESTE DE DIFERENTES MODELOS")
    print("="*60)

    models = ["gpt-4o-mini", "claude-3-5-sonnet-20241022"]

    data = {
        'VENDAS': [1000, 1500, 800, 2000],
        'MES': ['Janeiro', 'Fevereiro', 'Março', 'Abril'],
        'REGIAO': ['Norte', 'Sul', 'Norte', 'Sul']
    }
    df_sample = pd.DataFrame(data)

    user_query = "Qual região teve mais vendas no total?"

    for model in models:
        print(f"\n--- Testando modelo: {model} ---")
        try:
            processing_agent = ProcessingAgentManager(model)
            context = prepare_processing_context(user_query, df_sample)
            result = await processing_agent.process_context(context)

            print(f"Sucesso: {result['success']}")
            if result['success']:
                print(f"Query sugerida: {result['suggested_query']}")
            else:
                print(f"Erro: {result['output']}")
        except Exception as e:
            print(f"Erro ao testar {model}: {e}")

if __name__ == "__main__":
    print("Testando Processing Agent...")
    asyncio.run(test_processing_agent())
    asyncio.run(test_processing_flow())
