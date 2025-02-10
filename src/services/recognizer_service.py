import webrtcvad
import whisper
import numpy as np
import proto.stt_pb2 as pb2
import proto.stt_pb2_grpc as pb2_grpc
from utils.logger import get_logger

log = get_logger("recognizer_service")


class RecognizerServicer(pb2_grpc.RecognizerServicer):
    def __init__(self, model_name="base", vad_mode=3, sample_rate=16000, frame_duration_ms=30, overlap_frames=1):
        # Загружаем модель Whisper
        self.model = whisper.load_model(model_name)
        # Инициализируем VAD (значение mode: 0 – минимальная агрессивность, 3 – максимальная)
        self.vad = webrtcvad.Vad(vad_mode)
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        # Размер кадра (в байтах), для 16-бит PCM (2 байта на сэмпл)
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000) * 2
        # Буфер для накопления входящего аудио
        self.audio_buffer = b""
        # Храним последние кадры для перекрытия между сегментами (например, 1 кадр)
        self.tail_frames = []
        self.overlap_frames = overlap_frames

        # Параметры для вызова Whisper, их можно обновлять через session_options
        self.whisper_options = {
            "language": None,  # Если None – автоопределение языка
            "task": "transcribe",
            # Дополнительные параметры (например, temperature, initial_prompt и т.д.) можно добавить сюда
        }

    def update_options_from_session(self, session_options):
        """Обновление параметров модели на основе настроек, переданных клиентом."""
        print("Получены настройки сессии:", session_options)
        if session_options.recognition_model:
            lang_opts = session_options.recognition_model.language_restriction
            if lang_opts.language_code:
                # Берём первый язык из списка
                self.whisper_options["language"] = lang_opts.language_code[0]
                print("Установлен язык для распознавания:", self.whisper_options["language"])
        # Здесь можно добавить обновление других опций (например, text_normalization)

    def buffer_audio(self, chunk_data):
        """Добавляет новый аудиочанк в буфер."""
        self.audio_buffer += chunk_data

    def get_frames(self):
        """
        Разбивает накопленное аудио на кадры фиксированного размера.
        Возвращает список кадров и сохраняет остаток в буфере.
        """
        frames = []
        offset = 0
        while offset + self.frame_size <= len(self.audio_buffer):
            frame = self.audio_buffer[offset:offset + self.frame_size]
            frames.append(frame)
            offset += self.frame_size
        # Сохраняем остаток для следующей итерации
        self.audio_buffer = self.audio_buffer[offset:]
        return frames

    def detect_speech_segments(self, frames):
        """
        На основе VAD выделяет сегменты, содержащие речь, с учётом перекрытия.
        Если в начале нового набора кадров есть сохранённые tail‑кадры,
        они добавляются к первому сегменту.
        """
        segments = []
        current_segment = []

        # Если остались tail-кадры с прошлого вызова, начинаем с них
        if self.tail_frames:
            current_segment.extend(self.tail_frames)
            self.tail_frames = []

        for frame in frames:
            is_speech = self.vad.is_speech(frame, self.sample_rate)
            if is_speech:
                current_segment.append(frame)
            else:
                if current_segment:
                    # Завершаем сегмент при обнаружении паузы
                    segments.append(b"".join(current_segment))
                    current_segment = []
        # Если в конце остался непустой сегмент – сохраняем часть его для перекрытия
        if current_segment:
            if len(current_segment) > self.overlap_frames:
                # Отдаем сегмент без последних overlap_frames, которые сохраняем для перекрытия
                segment_without_overlap = current_segment[:-self.overlap_frames]
                segments.append(b"".join(segment_without_overlap))
                self.tail_frames = current_segment[-self.overlap_frames:]
            else:
                # Если сегмент слишком короткий – сохраняем полностью для будущего объединения
                self.tail_frames = current_segment

        return segments

    def pcm_to_float_np(self, segment):
        """
        Преобразует 16-битный PCM-байтовый объект в numpy-массив с плавающей точкой.
        """
        audio_np = np.frombuffer(segment, np.int16).astype(np.float32) / 32768.0
        return audio_np

    def transcribe_segment(self, audio_np):
        """
        Выполняет распознавание аудио с использованием модели Whisper.
        """
        try:
            result = self.model.transcribe(audio_np, **self.whisper_options)
            text = result.get("text", "").strip()
        except Exception as e:
            print("Ошибка при распознавании сегмента:", e)
            text = ""
        return text

    def build_response(self, text):
        """
        Формирует StreamingResponse на основе распознанного текста.
        """
        alternative = pb2.Alternative(
            text=text,
            confidence=0.9  # Здесь можно рассчитать реальную уверенность
        )
        alt_update = pb2.AlternativeUpdate(
            alternatives=[alternative],
            channel_tag="default"
        )
        response = pb2.StreamingResponse(
            final=alt_update,
            session_id="session-123"  # Можно заменить на уникальный идентификатор сессии
        )
        return response

    def RecognizeStreaming(self, request_iterator, context):
        """
        Основной метод gRPC‑сервиса.
        Обрабатывает входящие запросы (настройки сессии или аудиочанки),
        накапливает аудио, разбивает на кадры, выделяет сегменты с речью,
        выполняет распознавание и отправляет ответы.
        """
        print("Получен потоковый запрос.")
        for request in request_iterator:
            # Обработка настроек сессии
            if request.HasField("session_options"):
                self.update_options_from_session(request.session_options)
                continue

            # Обработка аудиочанка
            if request.HasField("chunk"):
                self.buffer_audio(request.chunk.data)
                frames = self.get_frames()
                if not frames:
                    continue

                segments = self.detect_speech_segments(frames)
                for segment in segments:
                    # Пропускаем слишком короткие сегменты
                    if len(segment) < self.frame_size:
                        continue
                    audio_np = self.pcm_to_float_np(segment)
                    transcribed_text = self.transcribe_segment(audio_np)
                    response = self.build_response(transcribed_text)
                    yield response
            else:
                print("Неизвестный тип сообщения в потоке.")
                continue
