import time

from services.start_service import create_server


def serve():
    server = create_server()
    server.start()
    print("gRPC сервер запущен на порту 50051")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        print("Остановка сервера")
        server.stop(0)


if __name__ == "__main__":
    serve()
