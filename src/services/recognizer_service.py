import asyncio
import random
import string
import time

import grpc
import proto.stt_pb2 as pb2
import proto.stt_pb2_grpc as pb2_grpc
from utils.logger import get_logger

log = get_logger("recognizer_service")

# Глобальный словарь для хранения сессий
session_tasks = {}


class RecognizerServicer(pb2_grpc.RecognizerServicer):
    def __init__(self):
        pass

    async def process_audio_task(self, session_id: str):
        """
        Фоновая задача, которая ожидает аудио-чанки из очереди,
        считает их и записывает номер обработанного чанка в очередь результатов.
        """
        session = session_tasks.get(session_id)
        if not session:
            log.error(f"Session {session_id} not found in process_audio_task")
            return

        audio_queue: asyncio.Queue = session["audio_queue"]
        result_queue: asyncio.Queue = session["result_queue"]
        chunk_count = 0

        while not session.get("stop", False):
            try:
                chunk = await asyncio.wait_for(audio_queue.get(), timeout=1.0)
                chunk_count += 1
                # Вместо обработки аудио записываем номер чанка в очередь результатов
                await result_queue.put(f"Получен чанк №{chunk_count}")
                log.info(f"Session {session_id}: Processed chunk {chunk_count}")
            except asyncio.TimeoutError:
                continue

        log.info(f"Audio processing task for session {session_id} has stopped.")

    async def CreateSession(self, request, context):
        while True:
            session_id = "".join(random.choices(string.ascii_letters + string.digits, k=10))
            if session_id not in session_tasks:
                break

        session = {
            "audio_queue": asyncio.Queue(),
            "result_queue": asyncio.Queue(),
            "stop": False,
            "start_time": time.time(),
        }
        session_tasks[session_id] = session

        asyncio.create_task(self.process_audio_task(session_id))
        log.info(f"Created session {session_id}")
        return pb2.SessionId(session_id=session_id)

    async def StreamingAudio(self, request_iterator, context):
        first_req = await anext(request_iterator, None)
        if not first_req or not first_req.options.session_id:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Первое сообщение должно содержать конфигурацию с session_id.")
            return pb2.StreamingAudioResponse(message="Неверная конфигурация сессии.")

        session_id = first_req.options.session_id
        session = session_tasks.get(session_id)
        if not session:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Сессия не найдена.")
            return pb2.StreamingAudioResponse(message="Сессия не найдена.")

        log.info(f"Session {session_id} started receiving audio.")

        # Читаем входящие аудио-чанки и помещаем их в очередь
        async for req in request_iterator:
            if hasattr(req, "chunk") and req.chunk:
                await session["audio_queue"].put(req.chunk)
                log.debug(f"Session {session_id}: Received an audio chunk.")

        # По окончании стрима отмечаем, что сессия завершена
        session["stop"] = True
        duration = time.time() - session["start_time"]
        log.info(f"Session {session_id} finished streaming audio. Duration: {duration:.2f} seconds.")
        return pb2.SessionInfo(duration=str(duration))

    async def GetRecognizeStream(self, request, context):
        """
        Стриминговый метод, который отправляет клиенту результаты обработки (номера чанков).
        Клиент передаёт session_id в запросе.
        """
        session_id = request.session_id
        session = session_tasks.get(session_id)
        if not session:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Сессия не найдена.")
            return

        result_queue: asyncio.Queue = session["result_queue"]

        log.info(f"Starting to stream recognized results for session {session_id}.")
        while not session.get("stop", False) or not result_queue.empty():
            try:
                result = await asyncio.wait_for(result_queue.get(), timeout=1.0)
                yield pb2.StreamingResponse(
                    session_id=session_id, final=pb2.AlternativeUpdate(channel_tag="channel_tag", alternatives=[pb2.Alternative(text="Привет", confidence=0.9)])
                )
                log.debug(f"Session {session_id}: Sent result: {result}")
            except asyncio.TimeoutError:
                # Если таймаут – проверяем активность соединения и продолжаем ожидание
                if not context.is_active():
                    break
                continue

        log.info(f"Finished streaming recognized results for session {session_id}.")
