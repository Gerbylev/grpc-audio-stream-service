import logging
import time
from config.Config import CONFIG
from utils.logger import get_logger
from services.start_service import create_server

log: logging = get_logger("MAIN")


def serve():
    server = create_server(port=CONFIG.server_port)
    server.start()
    log.info(f"Server start on port {CONFIG.server_port}")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        log.info(f"Server stop on port {CONFIG.server_port}")
        server.stop(0)


if __name__ == "__main__":
    serve()
