import asyncio

from config.Config import CONFIG
from services.start_service import create_server


def serve():
    asyncio.run(create_server(port=CONFIG.server_port))


if __name__ == "__main__":
    serve()
