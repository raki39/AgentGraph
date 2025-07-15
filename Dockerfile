# AgentGraph - Dockerfile Simples
FROM python:3.11-slim

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Diretório de trabalho
WORKDIR /app

# Copiar e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY agents/ ./agents/
COPY graphs/ ./graphs/
COPY nodes/ ./nodes/
COPY utils/ ./utils/
COPY app.py .

# Copiar arquivo CSV necessário para inicialização
COPY tabela.csv .

# Criar diretórios necessários
RUN mkdir -p uploaded_data

# Expor porta
EXPOSE 7860

# Comando de inicialização
CMD ["python", "app.py"]
