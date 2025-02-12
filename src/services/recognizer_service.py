import asyncio
import random
import string
import time
import wave

import grpc
import webrtcvad
import whisper
import numpy as np
import proto.stt_pb2 as pb2
import proto.stt_pb2_grpc as pb2_grpc
from utils.context_var import request_id_var
from utils.logger import get_logger

log = get_logger("recognizer_service")
request_id = 0

session_tasks = {}


class RecognizerServicer(pb2_grpc.RecognizerServicer):
    def __init__(self):
        pass

    async def process_audio_task(self, session_id):
        session = session_tasks.get(session_id)
        if session is None:
            return
        queue = session["queue"]
        while not session.get("stop", False):
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=1.0)
                if isinstance(chunk, bytes):
                    chunk = chunk.decode("utf-8")
                session["buffer"] += chunk
            except asyncio.TimeoutError:
                continue
        print(f"Задача для сессии {session_id} завершена.")

    async def CreateSession(self, request, context):
        while True:
            session_id = "".join(random.choices(string.ascii_letters + string.digits, k=10))
            if session_id not in session_tasks:
                break
        session = {
            "buffer": "",
            "queue": asyncio.Queue(),
            "stop": False,
            "start_time": None,
            "end_time": None,
        }
        session_tasks[session_id] = session
        asyncio.create_task(self.process_audio_task(session_id))
        return pb2.SessionId(session_id=session_id)

    async def StreamingAudio(self, request_iterator, context):
        # try:
        first_req = await anext(request_iterator, None)
        if not first_req.options.session_id:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Первое сообщение должно содержать конфигурацию")
            return

            # except StopIteration:
        #     context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
        #     context.set_details('No requests received')
        #     return pb2.StreamingAudioResponse(message="No data")
        #
        session_id = first_req.options.session_id
        session = session_tasks.get(session_id)
        if not session:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Session not found")
            return pb2.StreamingAudioResponse(message="Session not found")

        session["start_time"] = time.time()
        i = 0
        async for req in request_iterator:
            if hasattr(req, "chunk"):
                print(i)
                i += 1
                session["queue"].put_nowait(req.chunk)

        session["end_time"] = time.time()
        return pb2.SessionInfo(duration="dsa")

    def stop_session(self, session_id):
        """Функция, останавливающая асинхронную задачу по завершению сессии."""
        if session_id in session_tasks:
            session_tasks[session_id]["stop"] = True

    def GetRecognizeStream(self, request_iterator, context):
        return super().GetRecognizeStream(request_iterator, context)
