import time
from concurrent import futures
import grpc

import proto.stt_pb2_grpc as pb2_grpc
from services.recognizer_service import RecognizerServicer


def create_server(port=50051, max_workers=10):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    pb2_grpc.add_RecognizerServicer_to_server(RecognizerServicer(), server)
    server.add_insecure_port(f'[::]:{port}')
    return server