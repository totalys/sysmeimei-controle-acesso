FROM python:3.11-slim

# Define o diretório de trabalho
WORKDIR /usr/src/app

# Instala dependências do sistema (caso alguma lib Python precise compilar)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia apenas o requirements.txt primeiro para aproveitar cache
COPY requirements.txt ./

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Define usuário não-root (mais seguro)
RUN useradd -m appuser
USER appuser

# Comando padrão
CMD ["python", "sysmeimei-ac-consumer.py"]
