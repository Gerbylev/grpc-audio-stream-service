import datetime
import logging

import proto.stt_pb2
from proto import stt_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RecognizerServicer(stt_pb2_grpc.RecognizerServicer):
    def RecognizeStreaming(self, request_iterator, context):
        """
        Реализация метода RecognizeStreaming.
        При первом сообщении ожидается session_options,
        далее – аудио чанки.
        В данном примере мы просто собираем данные и возвращаем заглушку.
        """
        logger.info("Начало сессии распознавания")
        total_audio = b""
        session_options_received = False

        for request in request_iterator:
            msg_type = request.WhichOneof("message")
            if msg_type == "session_options":
                session_options_received = True
                logger.info("Получены session_options: %s", request.session_options)
            elif msg_type == "chunk":
                logger.info("Получен аудио-чанк длиной: %d байт", len(request.chunk.data))
                total_audio += request.chunk.data
            else:
                logger.info("Получено неизвестное сообщение: %s", msg_type)

        # Пример заглушки: возвращаем фиксированный результат распознавания.
        # Здесь вы позже добавите свою логику обработки total_audio.
        response = stt_pb2.StreamingResponse()
        # Заполняем поле final с альтернативой (dummy результат)
        alt = response.final.alternatives.add()
        alt.text = "Распознанный текст (заглушка)"
        alt.confidence = 1.0
        response.final.channel_tag = "0"
        response.session_id = "dummy-session-id-" + datetime.datetime.now().isoformat()

        logger.info("Отправка ответа: %s", response)
        yield response
