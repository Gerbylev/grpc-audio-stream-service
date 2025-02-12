from concurrent import futures
import grpc

import proto.stt_pb2_grpc as pb2_grpc
from services.recognizer_service import RecognizerServicer
from utils.logger import get_logger

log = get_logger("START")


async def create_server(port=50051):
    server = grpc.aio.server()
    pb2_grpc.add_RecognizerServicer_to_server(RecognizerServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    log.info(f"Server start on port {port}")
    await server.start()
    await server.wait_for_termination()
