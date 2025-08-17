from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from zoneinfo import ZoneInfo
import json, os, pika, socket
import time

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))  # Porta do servidor HTTP parametrizada
QUEUE_NAME = os.getenv("QUEUE_NAME", "lar_meimei_access")

connection = None
channel = None
credentials = pika.PlainCredentials(
    os.getenv("RABBITMQ_USER"),
    os.getenv("RABBITMQ_PASS")
)

def connect_rabbitmq():
    global connection, channel, credentials
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
        print("[✓] Conectado ao RabbitMQ!")
        return True
    except Exception as e:
        print(f"[!] Não foi possível conectar ao RabbitMQ: {e}")
        connection = None
        channel = None
        return False

# Tenta conectar ao iniciar
connect_rabbitmq()

def publish_message(perfil: str, area: str, payload: dict):
    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    payload["attendance_date"] = agora.strftime("%Y-%m-%d")
    payload["attendance_time"] = agora.strftime("%H:%M:%S")

    global channel
    retry_delays = [1, 5, 10]  # segundos

    for attempt, delay in enumerate(retry_delays, start=1):
        if channel is None or getattr(channel, "is_closed", False):
            print(f"[!] Canal RabbitMQ desconectado, tentativa {attempt} de reconexão...", flush=True)
            if not connect_rabbitmq():
                print(f"[!] Falha ao reconectar. Aguardando {delay}s antes da próxima tentativa...", flush=True)
                time.sleep(delay)
                continue
        try:
            channel.basic_publish(
                exchange="",
                routing_key=QUEUE_NAME,
                body=json.dumps(payload),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    headers={
                        "perfil": perfil,
                        "area": area
                    }
                )
            )
            print(f"[→] Mensagem publicada: perfil={perfil}, area={area}, payload={payload}", flush=True)
            return  # sucesso, não precisa tentar mais
        except Exception as e:
            print(f"[!] Falha ao publicar no RabbitMQ (tentativa {attempt}): {e}", flush=True)
            channel = None
            print(f"[!] Aguardando {delay}s antes da próxima tentativa...", flush=True)
            time.sleep(delay)

    # Se chegou aqui, todas as tentativas falharam
    print("[!] Todas as tentativas de publicação falharam. Salvando localmente.", flush=True)
    save_locally(payload)

def save_locally(payload):
    agora = datetime.now()
    dia = agora.strftime("%d-%m-%y")
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(log_dir, f"acessos_{dia}.log")
    try:
        with open(log_filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
        print(f"[→] Payload salvo localmente em {log_filename}")
    except Exception as file_error:
        print(f"[!] Falha ao salvar localmente: {file_error}")

class QRCodeRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Verifica se o caminho da requisição é o esperado (opcional)
        if self.path == '/test.py':
            # Obtém o tamanho dos dados recebidos
            content_length = int(self.headers['Content-Length'])
            # Lê os dados recebidos
            post_data = self.rfile.read(content_length)

            try:
                # Tenta decodificar como JSON (se o leitor enviar nesse formato)
                data = json.loads(post_data.decode('utf-8'))
                # print("Dados recebidos:", data)
                # Publica mensagem
                publish_message(data.get("perfil", None), data.get("area", None),data)
                
                # Resposta de sucesso
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = json.dumps({"status": "success", "message": "QR code received"})
                self.wfile.write(response.encode('utf-8'))
                
            except Exception as e:
                print("Erro ao processar requisição:", e)
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = json.dumps({"status": "error", "message": str(e)})
                self.wfile.write(response.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def get_host_ip():
    try:
        # Tenta descobrir o IP do host na rede local
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "IP_DO_HOST"

def run_server(port=8000):
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, QRCodeRequestHandler)
    host_ip = get_host_ip()
    print(f"Servidor iniciado na porta {port}")
    print(f"Acesse o endpoint via: http://{host_ip}:{port}/test.py (use o IP do host na rede local)", flush=True)
    httpd.serve_forever()
    connection.close()

if __name__ == '__main__':
    run_server()