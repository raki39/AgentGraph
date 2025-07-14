# Plano de Integração FastAPI - AgentGraph Backend

## Visão Geral

Este documento detalha a transformação do AgentGraph (sistema atual baseado em Gradio + LangGraph) em um backend empresarial robusto usando FastAPI. O objetivo é manter toda a funcionalidade existente dos agentes inteligentes enquanto adiciona capacidades de produção como autenticação, multi-usuário, escalabilidade e segurança.

### O que é o AgentGraph Atual

O AgentGraph é uma plataforma de agentes de IA que processa consultas em linguagem natural sobre dados CSV. Principais características:

- **Agentes Inteligentes**: SQL Agent (consultas em dados) + Processing Agent (otimização de contexto)
- **Multi-LLM**: Suporte a OpenAI, Anthropic e HuggingFace
- **Processamento Inteligente**: Upload de CSV, detecção automática de tipos, geração de gráficos
- **Interface Atual**: Gradio web interface para uso individual

### Por que FastAPI

Precisamos evoluir para um sistema empresarial que suporte:
- Múltiplos usuários simultâneos
- Autenticação e controle de acesso
- Processamento em background
- Escalabilidade horizontal
- APIs para integração com outras aplicações

## Arquitetura do Sistema Atual

### Componentes Principais

**1. LangGraph (Orquestração)**
- StateGraph com nós especializados
- Fluxo: Validação → Cache → Processing Agent → SQL Agent → Gráficos → Refinamento

**2. Agentes Inteligentes**
- **SQL Agent**: Executa consultas em dados CSV convertidos para SQLite
- **Processing Agent**: Otimiza contexto e sugere queries SQL

**3. Sistema de Nós Modulares**
- Validação de entrada
- Gerenciamento de cache
- Processamento de CSV
- Geração de gráficos
- Refinamento de respostas

**4. Gerenciadores**
- **Object Manager**: Objetos não-serializáveis (agentes, engines)
- **Cache Manager**: Cache inteligente de consultas

### Fluxo Atual Simplificado

```
Usuário → Gradio → LangGraph → [Processing Agent] → SQL Agent → Resposta
                      ↓              ↓                    ↓
                   Cache Check → Contexto Otimizado → Dados CSV
```

## Arquitetura do Backend FastAPI

### Estrutura Organizada

O backend será estruturado em camadas claras para facilitar manutenção e escalabilidade:

```
fastapi-backend/
├── app/
│   ├── main.py                    # Aplicação FastAPI principal
│   ├── core/                      # Configurações centrais
│   │   ├── config.py              # Variáveis de ambiente
│   │   ├── security.py            # JWT e criptografia
│   │   └── database.py            # Conexões de banco
│   ├── api/v1/                    # Endpoints da API
│   │   ├── auth.py                # Login, registro, tokens
│   │   ├── agents.py              # Gestão de agentes IA
│   │   ├── queries.py             # Execução de consultas
│   │   ├── files.py               # Upload de CSV/dados
│   │   └── admin.py               # Painel administrativo
│   ├── services/                  # Lógica de negócio
│   │   ├── auth_service.py        # Autenticação e usuários
│   │   ├── agent_service.py       # Integração com AgentGraph
│   │   ├── file_service.py        # Processamento de arquivos
│   │   └── queue_service.py       # Filas de processamento
│   ├── models/                    # Modelos de banco (SQLAlchemy)
│   │   ├── user.py                # Usuários e roles
│   │   ├── agent.py               # Configurações de agentes
│   │   └── session.py             # Sessões e histórico
│   ├── schemas/                   # Validação de dados (Pydantic)
│   │   ├── auth.py                # Login, registro
│   │   ├── agent.py               # Criação/edição de agentes
│   │   └── query.py               # Consultas e respostas
│   └── agentgraph/                # Código atual integrado
│       ├── graphs/                # LangGraph (adaptado)
│       ├── agents/                # SQL + Processing Agents
│       └── nodes/                 # Nós especializados
├── tests/                         # Testes automatizados
├── docker/                        # Containerização
└── alembic/                       # Migrações de banco
```

### Camadas do Sistema

**1. API Layer (Endpoints)**
- Recebe requisições HTTP
- Valida dados de entrada
- Retorna respostas padronizadas

**2. Service Layer (Lógica de Negócio)**
- Processa regras de negócio
- Integra com AgentGraph
- Gerencia filas e cache

**3. Data Layer (Persistência)**
- PostgreSQL para metadados
- SQLite para dados de usuário
- Redis para cache e filas

**4. AgentGraph Integration**
- Código atual adaptado
- Multi-usuário
- Processamento assíncrono

## Endpoints da API

### Autenticação e Usuários

**Endpoints de Registro e Login:**
- POST /api/v1/auth/register - Criar nova conta
- POST /api/v1/auth/login - Fazer login
- POST /api/v1/auth/refresh-token - Renovar token
- POST /api/v1/auth/logout - Fazer logout

**Gestão de Perfil:**
- GET /api/v1/users/me - Ver perfil atual
- PUT /api/v1/users/me - Atualizar perfil
- DELETE /api/v1/users/me - Excluir conta

**Funcionamento:**
O usuário envia email e senha para login, recebe tokens JWT de acesso e renovação, além dos dados do perfil incluindo role de permissão.

### Gestão de Agentes

**CRUD de Agentes:**
- GET /api/v1/agents/ - Lista agentes do usuário
- POST /api/v1/agents/ - Cria novo agente
- GET /api/v1/agents/{agent_id} - Detalhes do agente
- PUT /api/v1/agents/{agent_id} - Atualiza agente
- DELETE /api/v1/agents/{agent_id} - Remove agente

**Configurações Avançadas:**
- POST /api/v1/agents/{agent_id}/clone - Clona agente existente
- GET /api/v1/agents/templates - Lista templates disponíveis

**Funcionalidades:**
Cada agente pode ser configurado com diferentes modelos LLM, ativação do Processing Agent, modo avançado de refinamento, e outras configurações específicas. Usuários podem criar múltiplos agentes especializados para diferentes tipos de análise.

### Execução de Consultas

**Consultas Síncronas (rápidas):**
- POST /api/v1/queries/execute - Executa consulta imediatamente

**Consultas Assíncronas (longas):**
- POST /api/v1/queries/execute-async - Inicia processamento em background
- GET /api/v1/queries/{query_id}/status - Verifica status da consulta
- GET /api/v1/queries/{query_id}/result - Obtém resultado quando pronto

**Histórico:**
- GET /api/v1/queries/history - Lista consultas anteriores
- GET /api/v1/queries/{query_id} - Detalhes de consulta específica

**Funcionalidades:**
As consultas podem gerar gráficos automaticamente, usar modo avançado de refinamento, e são processadas pelos agentes configurados. Consultas longas são executadas em filas para não bloquear a interface.

### Gestão de Dados e Conexões

**Upload de Arquivos:**
- POST /api/v1/files/upload - Upload chunked de arquivos CSV
- GET /api/v1/files/ - Lista arquivos do usuário
- DELETE /api/v1/files/{file_id} - Remove arquivo
- GET /api/v1/files/{file_id}/status - Status do processamento
- GET /api/v1/files/{file_id}/preview - Preview dos dados

**Conexões de Banco de Dados:**
- POST /api/v1/databases/connect - Conecta banco externo (MySQL, PostgreSQL, etc.)
- GET /api/v1/databases/ - Lista conexões do usuário
- PUT /api/v1/databases/{db_id} - Atualiza configuração de conexão
- DELETE /api/v1/databases/{db_id} - Remove conexão
- POST /api/v1/databases/{db_id}/test - Testa conectividade
- GET /api/v1/databases/{db_id}/tables - Lista tabelas disponíveis
- GET /api/v1/databases/{db_id}/schema - Obtém schema das tabelas

**Funcionalidades:**
Sistema híbrido que permite tanto upload de CSV (convertido para SQLite) quanto conexão direta com bancos externos. Processamento paralelo otimizado para múltiplos usuários simultâneos. Suporte a MySQL, PostgreSQL, SQL Server e outros bancos relacionais.

### Sistema de Roles e Permissões

**Gestão de Roles (Admin/Master):**
- GET /api/v1/roles/ - Lista roles disponíveis
- POST /api/v1/roles/ - Cria nova role personalizada
- PUT /api/v1/roles/{role_id} - Atualiza role
- DELETE /api/v1/roles/{role_id} - Remove role
- GET /api/v1/roles/{role_id}/permissions - Lista permissões da role

**Gestão de Usuários:**
- GET /api/v1/users/ - Lista usuários (conforme permissão)
- POST /api/v1/users/ - Cria novo usuário
- PUT /api/v1/users/{user_id} - Atualiza usuário
- DELETE /api/v1/users/{user_id} - Remove usuário
- PUT /api/v1/users/{user_id}/role - Altera role do usuário
- GET /api/v1/users/{user_id}/permissions - Permissões específicas do usuário

**Tipos de Usuário:**
- **ADMIN**: Controle total do sistema (você)
- **MASTER**: Pode criar roles e gerenciar usuários normais
- **NORMAL**: Usuário final com permissões definidas por roles

### Histórico e Contextualização

**Gestão de Sessões:**
- GET /api/v1/sessions/ - Lista sessões do usuário
- POST /api/v1/sessions/ - Inicia nova sessão
- GET /api/v1/sessions/{session_id} - Detalhes da sessão
- PUT /api/v1/sessions/{session_id}/resume - Retoma sessão pausada
- DELETE /api/v1/sessions/{session_id} - Encerra sessão

**Histórico de Conversas:**
- GET /api/v1/sessions/{session_id}/messages - Histórico da conversa
- POST /api/v1/sessions/{session_id}/messages - Adiciona mensagem
- GET /api/v1/history/search - Busca no histórico por contexto
- GET /api/v1/history/stats - Estatísticas de uso

**Contextualização Inteligente:**
- GET /api/v1/context/{session_id} - Contexto atual da sessão
- POST /api/v1/context/index - Indexa conversa para busca
- GET /api/v1/context/similar - Encontra conversas similares

### Administração Avançada

**Métricas e Monitoramento:**
- GET /api/v1/admin/metrics - Métricas detalhadas do sistema
- GET /api/v1/admin/system-health - Status de saúde completo
- GET /api/v1/admin/audit-logs - Logs de auditoria
- GET /api/v1/admin/performance - Métricas de performance
- GET /api/v1/admin/costs - Análise de custos por usuário/LLM

## Como Funciona a Integração

### Processo de Integração

**1. Preservação do Código Atual**
- Todo o código do AgentGraph será mantido na pasta `/app/agentgraph/`
- Nenhuma funcionalidade será perdida
- Agentes continuam funcionando exatamente igual

**2. Adaptações Necessárias**

O sistema atual funciona para um usuário por vez. Precisamos adaptar para:
- Múltiplos usuários simultâneos
- Isolamento de dados por usuário
- Processamento assíncrono
- Cache compartilhado com segurança

**3. Fluxo Integrado**

Cliente → FastAPI → Autenticação → AgentGraph → Resposta

Cada requisição passa por autenticação JWT, identifica o usuário, acessa seus dados isolados, executa o AgentGraph e retorna resultado em JSON.

### Principais Mudanças

**Object Manager Multi-usuário:**
Cada usuário terá seu próprio Object Manager isolado, garantindo que agentes, cache e dados não se misturem entre usuários diferentes. Suporte a múltiplas conexões de banco por usuário.

**Sistema de Roles Complexo:**
Três níveis hierárquicos de usuário com roles personalizáveis. MASTER pode criar roles específicas para NORMAL, definindo permissões granulares para cada funcionalidade.

**Conexões Multi-Banco:**
Sistema híbrido que suporta tanto CSV uploadado quanto conexões diretas com bancos externos. Cada usuário pode ter múltiplas fontes de dados ativas simultaneamente.

**Histórico Contextualizado:**
Sistema avançado de sessões persistentes com indexação para busca semântica. Usuários podem retomar conversas exatamente onde pararam, com contexto completo preservado.

**Processamento Ultra-Otimizado:**
Filas Celery especializadas para diferentes tipos de operação (upload, consulta, conexão de banco), com processamento paralelo otimizado para máxima performance.

## Sistemas Obrigatórios Resumidos

### 1. Sistema de Autenticação e Roles Complexo
- Três níveis de usuário: ADMIN, MASTER, NORMAL
- Roles personalizáveis criadas por MASTER
- Permissões granulares por funcionalidade
- JWT com refresh tokens e middleware de proteção

### 2. Conexões Multi-Banco de Dados
- Suporte a CSV → SQLite (upload)
- Conexão direta com MySQL, PostgreSQL, SQL Server
- Gerenciamento de múltiplas conexões por usuário
- Teste de conectividade e validação de schema

### 3. Sistema Multi-usuário Ultra-Otimizado
- Processamento paralelo para todos os componentes
- Isolamento total de dados e recursos
- Filas Celery otimizadas para uploads e consultas
- Pool de conexões inteligente por usuário

### 4. Histórico e Contextualização Avançada
- Sessões persistentes com retomada
- Indexação de conversas para busca contextual
- Histórico completo de interações
- Busca semântica em conversas anteriores

### 5. Gestão de Dados Híbrida
- **PostgreSQL**: Sistema, usuários, roles, sessões
- **SQLite**: Dados CSV isolados por usuário
- **Bancos Externos**: Conexões diretas configuráveis
- **Redis**: Cache e filas de processamento

### 6. Sistema Administrativo Multi-Nível
- ADMIN: Controle total do sistema
- MASTER: Criação de roles e gestão de usuários
- Monitoramento detalhado por usuário e recurso
- Análise de custos e performance granular

## Cronograma Simplificado

**Fase 1 (3 semanas): Base**
- FastAPI + PostgreSQL + JWT
- Estrutura básica de usuários e roles

**Fase 2 (4 semanas): Integração Complexa**
- Adaptação do AgentGraph para multi-usuário
- Sistema de roles personalizáveis
- Conexões multi-banco de dados
- Cache Redis com isolamento

**Fase 3 (5 semanas): Sistemas Avançados**
- Histórico contextualizado e sessões persistentes
- Filas Celery ultra-otimizadas
- Sistema de busca semântica
- Painel administrativo multi-nível

**Fase 4 (3 semanas): Finalização**
- Testes automatizados completos
- Otimizações de performance avançadas
- Monitoramento granular
- Deploy e documentação

**Total: 15 semanas**

## Resumo Executivo

**O que estamos fazendo:**
Transformar o AgentGraph (sistema individual com Gradio) em um backend empresarial robusto que suporte múltiplos usuários, autenticação, escalabilidade e integração com outras aplicações.

**O que será mantido:**
- 100% da funcionalidade dos agentes IA
- Todos os LLMs suportados (OpenAI, Anthropic, HuggingFace)
- Sistema de processamento de CSV
- Geração de gráficos
- Cache inteligente

**O que será adicionado:**
- Sistema complexo de usuários com roles personalizáveis
- Conexões multi-banco de dados (CSV + MySQL + PostgreSQL + outros)
- Processamento ultra-otimizado e paralelo
- Histórico contextualizado com busca semântica
- Sessões persistentes com retomada
- Painel administrativo multi-nível
- Monitoramento granular e análise de custos
- Escalabilidade horizontal com isolamento total

**Resultado final:**
Um sistema empresarial robusto que mantém toda a inteligência do AgentGraph atual, mas com capacidades avançadas para suportar centenas de usuários simultâneos, múltiplas fontes de dados, roles personalizáveis, e histórico contextualizado, tudo com performance otimizada e segurança empresarial.


