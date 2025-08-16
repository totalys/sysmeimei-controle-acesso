from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import json, os, pika, time, socket

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
            pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials)
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
    agora = datetime.now()
    payload["attendance_date"] = agora.strftime("%Y-%m-%d")
    payload["attendance_time"] = agora.strftime("%H:%M:%S")

    global channel
    if channel is None:
        # Tenta reconectar antes de desistir
        if not connect_rabbitmq():
            save_locally(payload)
            return

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
    except Exception as e:
        print(f"[!] Falha ao publicar no RabbitMQ: {e}")
        # Marca canal como indisponível
        channel = None
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