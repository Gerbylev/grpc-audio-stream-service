import datetime
import logging

from proto import stt_pb2
from proto import stt_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RecognizerServicer(stt_pb2_grpc.RecognizerServicer):
    def RecognizeStreaming(self, request_iterator, context):
        print("Получен потоковый запрос.")
        for request in request_iterator:
            print("Обработка запроса:", request)
            # Заглушка: возвращаем dummy-ответ для каждого полученного запроса
            response = stt_pb2.StreamingResponse(session_id="dummy-session-id")
            yield response