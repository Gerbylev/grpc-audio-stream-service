import pytest
import grpc
import time
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
async def test_recognize_streaming(grpc_channel):

    stub = pb2_grpc.RecognizerStub(grpc_channel)

    def request_generator():
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
        yield pb2.StreamingRequest(chunk=pb2.AudioChunk(data=b"\x00\x01"))
        yield pb2.StreamingRequest(chunk=pb2.AudioChunk(data=b"\x00\x01"))
        yield pb2.StreamingRequest(chunk=pb2.AudioChunk(data=b"\x00\x01"))

    responses = stub.RecognizeStreaming(request_generator())
    response_list = list(responses)
    assert len(response_list) >= 1
    assert response_list[0].session_id == "dummy-session-id"
