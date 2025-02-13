import asyncio
import pytest
import soundfile as sf
import grpc
import proto.stt_pb2 as pb2
import proto.stt_pb2_grpc as pb2_grpc


@pytest.fixture
async def grpc_channel():
    channel = grpc.aio.insecure_channel("localhost:50051")
    yield channel
    await channel.close()


@pytest.mark.asyncio
async def test_recognize_streaming_with_audio_file(grpc_channel):
    stub = pb2_grpc.RecognizerStub(grpc_channel)

    session_response = await stub.CreateSession(pb2.CreateSessionInfo(emails=["gerbylev.oleg@gmail.com"]))
    session_id = session_response.session_id

    data, sr = sf.read("data/segment.flac", dtype="int16")
    if data.ndim > 1:
        data = data[:, 0]
    raw_bytes = data.tobytes()

    def request_generator():
        # Первое сообщение содержит конфигурацию с session_id
        yield pb2.StreamingRequest(options=pb2.StreamingOptions(session_id=session_id))
        chunk_size = 1024  # можно подбирать оптимальный размер чанка
        for i in range(0, len(raw_bytes), chunk_size):
            chunk = raw_bytes[i : i + chunk_size]
            yield pb2.StreamingRequest(chunk=pb2.AudioChunk(data=chunk, channel_id="1"))

    # Запускаем отправку аудио-чанков через StreamingAudio в виде асинхронной задачи
    audio_task = asyncio.create_task(request_generator())

    # Параллельно запускаем чтение стрима результатов из GetRecognizeStream
    recognized_messages = []
    async for response in stub.GetRecognizeStream(pb2.SessionConfiguration(session_id=session_id, language_code="ru")):
        recognized_messages.append(response.message)
        if len(recognized_messages) >= 3:
            break

    session_info = await audio_task

    assert len(recognized_messages) > 0, "Не получено ни одного сообщения распознавания."
    for msg in recognized_messages:
        assert "Получен чанк №" in msg, f"Неверное сообщение: {msg}"

    # Можно вывести для отладки:
    print("Session duration:", session_info.duration)
    print("Recognized messages:", recognized_messages)
