import pytest
import grpc
import time
import soundfile as sf

import proto.stt_pb2 as pb2
import proto.stt_pb2_grpc as pb2_grpc
from services.start_service import create_server


@pytest.fixture(scope="module")
def grpc_server():
    server = create_server(port=50052)
    server.start()
    time.sleep(0.5)
    yield server
    server.stop(0)


@pytest.fixture
def grpc_channel(grpc_server):
    channel = grpc.insecure_channel("localhost:50052")
    yield channel
    channel.close()


@pytest.mark.asyncio
async def test_recognize_streaming_with_audio_file(grpc_channel):
    stub = pb2_grpc.RecognizerStub(grpc_channel)

    # Читаем аудиофайл с помощью soundfile
    data, sr = sf.read("data/segment.flac", dtype='int16')
    # Если аудио имеет несколько каналов, оставляем первый канал
    if data.ndim > 1:
        data = data[:, 0]
    # Предполагаем, что sample_rate уже равен 16000; иначе необходимо выполнить ресемплирование
    raw_bytes = data.tobytes()

    def request_generator():
        # Передаём настройки сессии
        yield pb2.StreamingRequest(
            session_options=pb2.StreamingOptions(
                recognition_model=pb2.RecognitionModelOptions(
                    audio_format=pb2.AudioFormatOptions(
                        raw_audio=pb2.RawAudio(
                            audio_encoding=pb2.RawAudio.LINEAR16_PCM,
                            sample_rate_hertz=16000,
                            audio_channel_count=1,
                        )
                    ),
                    text_normalization=pb2.TextNormalizationOptions(
                        text_normalization=pb2.TextNormalizationOptions.TEXT_NORMALIZATION_ENABLED,
                        profanity_filter=True,
                        literature_text=False,
                    ),
                    language_restriction=pb2.LanguageRestrictionOptions(
                        restriction_type=pb2.LanguageRestrictionOptions.WHITELIST,
                        language_code=["en", "ru"],
                    ),
                )
            )
        )
        # Разбиваем аудио на чанки и отправляем
        chunk_size = 1024  # можно подобрать оптимальный размер чанка
        for i in range(0, len(raw_bytes), chunk_size):
            chunk = raw_bytes[i:i+chunk_size]
            yield pb2.StreamingRequest(chunk=pb2.AudioChunk(data=chunk))

    responses = stub.RecognizeStreaming(request_generator())
    response_list = list(responses)

    # Проверяем, что получили хотя бы один ответ
    assert len(response_list) >= 1
    # Проверяем идентификатор сессии (может возвращаться "dummy-session-id" или "session-123" в зависимости от реализации)
    assert response_list[0].session_id in ["dummy-session-id", "session-123"]
