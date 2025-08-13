import os
import json
import pika
from datetime import datetime, timedelta
import time

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
QUEUE_NAME = os.getenv("QUEUE_NAME", "lar_meimei_access")
LOG_DIR = os.getenv("LOG_DIR", "logs")

def connect_rabbitmq():
    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT)
            )
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            return connection, channel
        except Exception as e:
            print(f"[!] Não foi possível conectar ao RabbitMQ: {e}")
            print("[*] Tentando novamente em 10 segundos...")
            time.sleep(10)

def reenfileirar_logs():
    hoje = datetime.now().strftime("%d-%m-%y")
    arquivos = [
        f for f in os.listdir(LOG_DIR)
        if f.startswith("acessos_") and f.endswith(".log")
    ]
    arquivos_a_processar = []
    for nome in arquivos:
        try:
            data_str = nome.replace("acessos_", "").replace(".log", "")
            # Só processa arquivos de datas anteriores ao dia de hoje
            if data_str < hoje:
                arquivos_a_processar.append(nome)
        except Exception:
            continue

    if not arquivos_a_processar:
        print(f"[i] Nenhum arquivo de log pendente para reenfileirar.")
        return

    connection, channel = connect_rabbitmq()
    for log_filename in sorted(arquivos_a_processar):
        log_path = os.path.join(LOG_DIR, log_filename)
        print(f"[i] Tentando reenfileirar registros de {log_path}...")
        reenfileirados = 0
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                linhas = f.readlines()
            for linha in linhas:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    payload = json.loads(linha)
                    channel.basic_publish(
                        exchange="",
                        routing_key=QUEUE_NAME,
                        body=json.dumps(payload),
                        properties=pika.BasicProperties(
                            delivery_mode=2,
                            headers={
                                "perfil": payload.get("perfil"),
                                "area": payload.get("area")
                            }
                        )
                    )
                    reenfileirados += 1
                except Exception as e:
                    print(f"[!] Falha ao reenfileirar linha: {linha}\nErro: {e}")
            if reenfileirados == len(linhas):
                os.remove(log_path)
                print(f"[✓] Todos os registros reenfileirados. Arquivo {log_path} removido.")
            else:
                print(f"[!] Nem todos os registros foram reenfileirados. Arquivo mantido para próxima tentativa.")
        except Exception as e:
            print(f"[!] Erro ao processar {log_path}: {e}")
    connection.close()

def aguardar_proxima_execucao():
    # Horários fixos em que o serviço deve rodar
    horarios = ["06:00", "15:00", "22:00"]
    while True:
        agora = datetime.now()
        proximos = []
        for h in horarios:
            hora, minuto = map(int, h.split(":"))
            proximo = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            if proximo <= agora:
                proximo += timedelta(days=1)
            proximos.append(proximo)
        proxima_execucao = min(proximos)
        segundos = (proxima_execucao - agora).total_seconds()
        print(f"[i] Próxima execução agendada para {proxima_execucao.strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(segundos)
        reenfileirar_logs()

if __name__ == "__main__": # Roda em loop nos horários
    print("[i] Serviço de reenfileiramento iniciado.")
    reenfileirar_logs()
    aguardar_proxima_execucao()
