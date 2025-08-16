# Controle de Acesso - Lar Meimei

> **Disclaimer:**  
> As variáveis de ambiente (como senhas, tokens e URLs) usadas neste projeto são apenas para **ambiente de desenvolvimento**.  
> **Nunca** utilize dados sensíveis diretamente em arquivos ou variáveis de ambiente em produção.  
> Para ambientes produtivos, utilize soluções seguras de gerenciamento de segredos, como HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, etc.

---

Este projeto implementa um sistema de controle de acessos baseado em microserviços, utilizando Python, Docker e RabbitMQ. Ele é composto por três serviços principais:

- **Produtor:** Recebe requisições HTTP de dispositivos de leitura de acesso, publica eventos em uma fila RabbitMQ ou salva localmente em caso de falha.
- **Consumidor:** Consome eventos da fila RabbitMQ e envia os dados para uma API externa. Em caso de erro, salva a mensagem em log e envia para uma fila de deadletter.
- **Retry-Logs:** Periodicamente, reenfileira registros de presença salvos em arquivos de log locais para o RabbitMQ, caso tenham ficado pendentes por indisponibilidade do serviço.

---

## Estrutura do Projeto

```
controle-acesso/
├── consumidor/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── sysmeimei-ac-consumer.py
├── produtor/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── sysmeimei-ac-server.py
├── retry/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── retry-logs.py
├── docker-compose.yml
```

---

## Como funciona

1. **Dispositivo de acesso** faz uma requisição HTTP POST para o serviço **produtor**.
2. O **produtor** tenta publicar a mensagem na fila do **RabbitMQ**.
   - Se não conseguir, salva o evento em um arquivo de log local.
3. O **consumidor** lê as mensagens da fila e envia para a API do Lar Meimei.
   - Se ocorrer erro, salva a mensagem em `logs/acessos_erros_DD-MM-YY.log` e envia para a fila de deadletter (`acessos_erros`).
4. O **retry-logs** roda automaticamente todos os dias às 6h, 15h e 22h, reenfileirando registros de presença salvos em arquivos de log de dias anteriores para o RabbitMQ.

---

## Como rodar

1. Certifique-se de ter Docker e Docker Compose instalados.
2. Execute:
   ```sh
   docker compose up --build
   ```
3. O serviço produtor ficará disponível na porta definida pela variável de ambiente `SERVER_PORT` (padrão: 8000) do host.

---

## Exemplo de requisição

```http
POST http://<IP_DO_HOST>:8000/test.py
Content-Type: application/json

{
  "perfil": "usuario",
  "area": "SF - Sócio Familiar",
  "nome": "Maria"
}
```

---

## Logs

- Se o RabbitMQ estiver indisponível, os acessos serão salvos em arquivos `logs/acessos_DD-MM-YY.log` no host.
- O consumidor salva mensagens com erro em `logs/acessos_erros_DD-MM-YY.log` e envia para a fila de deadletter `acessos_erros`.
- O serviço **retry-logs** processa todos os arquivos de log de dias anteriores, reenfileirando os registros para o RabbitMQ e removendo os arquivos após o sucesso.

---

## Diagrama de Sequência

```mermaid
sequenceDiagram
    box rgba(140, 250, 130, 0.5) Portaria
    participant Dispositivo
    end
    box rgba(238, 133, 133, 0.1) Servidor local
    participant Produtor
    participant RabbitMQ
    participant Consumidor
    participant RetryLogs
    end
    box rgba(129, 159, 255, 0.16) cloud
    participant Sysmeimei 2.0
    end

    Dispositivo->>Produtor: HTTP POST /test.py (dados do acesso)
    alt RabbitMQ disponível
        Produtor->>RabbitMQ: Publica mensagem
    else RabbitMQ indisponível
        Produtor->>Produtor: Salva em logs/acessos_DD-MM-YY.log
    end
    RabbitMQ-->>Consumidor: Mensagem de acesso
    Consumidor->>Sysmeimei 2.0: POST dados do acesso
    Sysmeimei 2.0-->>Consumidor: Resposta

    alt Erro no consumidor
        Consumidor->>Consumidor: Salva em<br>logs/acessos_erros_DD-MM-YY.log
        Consumidor->>RabbitMQ: Envia para fila de deadletter<br> (acessos_erros)
    end

    loop 6h, 15h, 22h
        RetryLogs->>RetryLogs: Lê arquivos de log antigos<br>logs/acessos_[D-1].log
        RetryLogs->>RabbitMQ: Reenfileira registros pendentes
        RetryLogs->>RetryLogs: Remove arquivos de log processados
    end
```

---

## Variáveis de ambiente importantes

- `RABBITMQ_HOST`: Host do RabbitMQ (use `rabbitmq` no docker-compose)
- `RABBITMQ_PORT`: Porta do RabbitMQ (padrão: 5672)
- `QUEUE_NAME`: Nome da fila principal (padrão: lar_meimei_access)
- `DEADLETTER_QUEUE`: Nome da fila de deadletter (padrão: acessos_erros)
- `SERVER_PORT`: Porta do servidor HTTP do produtor (padrão: 8000)
- `LOG_DIR`: Diretório dos arquivos de log (padrão: logs)
- `EMPLOYEE_URL`, `CUSTOMER_URL`, `POST_HEADERS`: URLs e headers para integração com API externa

---

## Observações

- O serviço produtor deve ser acessado pelo IP do host na rede local, não pelo IP do container.
- Os arquivos de log são persistidos no host via volume Docker.
- O serviço retry-logs garante que nenhum acesso será perdido mesmo com RabbitMQ fora.
- Mantenha os arquivos `requirements.txt` atualizados em cada serviço para garantir o correto funcionamento dos containers.
- **Em produção, nunca exponha dados sensíveis em variáveis de ambiente ou arquivos versionados. Use vaults!**

---

## docker-compose.yml (exemplo)

```yaml
version: "3.9"

services:
  produtor:
    build: ./produtor
    container_name: produtor
    depends_on:
      - rabbitmq
    environment:
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_PORT=5672
      - RABBITMQ_USER=lm_access
      - RABBITMQ_PASS=lm_access
      - SERVER_PORT=8000
      - QUEUE_NAME=lar_meimei_access
    ports:
      - "8000:8000"
    volumes:
      - ./produtor/logs:/usr/src/app/logs
    command: python -u sysmeimei-ac-server.py

  consumidor:
    build: ./consumidor
    container_name: consumidor
    depends_on:
      - rabbitmq
    environment:
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_PORT=5672
      - RABBITMQ_USER=lm_access
      - RABBITMQ_PASS=lm_access
      - QUEUE_NAME=lar_meimei_access
      - DEADLETTER_QUEUE=acessos_erros
      - POST_HEADERS={"Content-Type":"application/json","token ****":"********","accept":"application/json"}
      - EMPLOYEE_URL=https://larmeimei.org/api/resource/LM%20Attendance
      - CUSTOMER_URL=https://larmeimei.org/api/resource/LM%20Attendance%20cst
    volumes:
      - ./consumidor/logs:/usr/src/app/logs
    command: python -u sysmeimei-ac-consumer.py

  rabbitmq:
    image: rabbitmq:3-management
    container_name: rabbitmq_server
    ports:
      - "5672:5672"
      - "15672:15672"
    volumes:
      - ./rabbitmq_data:/var/lib/rabbitmq
      - ./rabbitmq/definitions.json:/etc/rabbitmq/definitions.json:ro
      - ./rabbitmq/rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
    environment:
      - RABBITMQ_DEFAULT_USER=admin
      - RABBITMQ_DEFAULT_PASS=admin

  retry-logs:
    build: ./retry
    container_name: retry-logs
    depends_on:
      - rabbitmq
    volumes:
      - ./produtor/logs:/usr/src/app/logs
    environment:
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_PORT=5672
      - RABBITMQ_USER=lm_access
      - RABBITMQ_PASS=lm_access
      - QUEUE_NAME=lar_meimei_access
      - LOG_DIR=logs
    command: python -u retry-
```