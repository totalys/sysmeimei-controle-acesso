import pika
import os
import json
import requests
import time
from datetime import datetime
from models import Employee, Student, Assistido

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
QUEUE_NAME = os.getenv("QUEUE_NAME", "lar_meimei_access")
DEADLETTER_QUEUE = os.getenv("DEADLETTER_QUEUE", "lar_meimei_access_errors")
EMPLOYEE_URL = os.getenv("EMPLOYEE_URL", "https://larmeimei.org/api/resource/LM%20Attendance")
CUSTOMER_URL = os.getenv("CUSTOMER_URL", "https://larmeimei.org/api/resource/LM%20Attendance%20cst")
POST_HEADERS = json.loads(os.getenv(
    "POST_HEADERS",
    '{"Content-Type": "application/json", "accept": "application/json"}'
))

# Registry de mapeamento (perfil, area) → classe
PROFILE_MAP = {
    ("voluntario", None): Employee,
    ("usuario", "MT - Mundo do Trabalho"): Student,
    ("usuario", "SF - Sócio Familiar"): Student,
    ("usuario", "gestantes"): Student,
    ("usuario_menor", "SF - Sócio Familiar"): Student,
    ("usuario", "cesta_basica"): Assistido,
}

def parse_message(perfil, area, data):
    key = (perfil, area if area else None)
    cls = PROFILE_MAP.get(key)
    if not cls:
        raise ValueError(f"Tipo de payload não mapeado: perfil={perfil}, area={area}")
    
    post_url = EMPLOYEE_URL if perfil == "voluntario" else CUSTOMER_URL
    
    return cls(**data), post_url

def send_to_api(obj, post_url):
    response = requests.post(post_url, headers=POST_HEADERS, json=obj.__dict__)
    print(f"[API] Status={response.status_code}, Body={response.text}")

def save_error_locally(payload):
    agora = datetime.now()
    dia = agora.strftime("%d-%m-%y")
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(log_dir, f"acessos_erros_{dia}.log")
    with open(log_filename, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")

def callback(ch, method, properties, body):
    try:
        perfil = properties.headers.get("perfil")
        area = properties.headers.get("area")
        payload = json.loads(body)
        obj, post_url = parse_message(perfil, area, payload)
        print(f"[✓] Recebido: {obj}", flush=True)
        send_to_api(obj, post_url)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"[!] Erro ao processar mensagem: {e}", flush=True)
        # Salva localmente
        save_error_locally(json.loads(body))
        # Envia para deadletter queue
        ch.basic_publish(
            exchange="",
            routing_key=DEADLETTER_QUEUE,
            body=body,
            properties=properties
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)

def main():

    credentials = pika.PlainCredentials(
        os.getenv("RABBITMQ_USER"),
        os.getenv("RABBITMQ_PASS")
    )

    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    port=RABBITMQ_PORT,
                    credentials=credentials,
                    heartbeat=30
                )
            )
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.queue_declare(queue=DEADLETTER_QUEUE, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
            print(f"[*] Aguardando mensagens na fila '{QUEUE_NAME}'...")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            print(f"[!] Não foi possível conectar ao RabbitMQ: {e}")
            print("[*] Tentando novamente em 5 segundos...")
            time.sleep(5)
        except Exception as e:
            print(f"[!] Erro inesperado: {e}")
            print("[*] Tentando novamente em 5 segundos...")
            time.sleep(5)

if __name__ == "__main__":
    main()
