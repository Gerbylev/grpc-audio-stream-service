import os

import numpy as np
import torchaudio
from scipy.io.wavfile import write


class VADIterator:
    def __init__(self,
                 model,
                 threshold: float = 0.5,
                 sampling_rate: int = 16000,
                 min_silence_duration_ms: int = 500,  # makes sense on one recording that I checked
                 speech_pad_ms: int = 100             # same
                 ):

        """
        Class for stream imitation

        Parameters
        ----------
        model: preloaded .jit silero VAD model

        threshold: float (default - 0.5)
            Speech threshold. Silero VAD outputs speech probabilities for each audio chunk, probabilities ABOVE this value are considered as SPEECH.
            It is better to tune this parameter for each dataset separately, but "lazy" 0.5 is pretty good for most datasets.

        sampling_rate: int (default - 16000)
            Currently silero VAD models support 8000 and 16000 sample rates

        min_silence_duration_ms: int (default - 100 milliseconds)
            In the end of each speech chunk wait for min_silence_duration_ms before separating it

        speech_pad_ms: int (default - 30 milliseconds)
            Final speech chunks are padded by speech_pad_ms each side
        """

        self.model = model
        self.threshold = threshold
        self.sampling_rate = sampling_rate

        if sampling_rate not in [8000, 16000]:
            raise ValueError('VADIterator does not support sampling rates other than [8000, 16000]')

        self.min_silence_samples = sampling_rate * min_silence_duration_ms / 1000
        self.speech_pad_samples = sampling_rate * speech_pad_ms / 1000
        self.reset_states()

    def reset_states(self):

        self.model.reset_states()
        self.triggered = False
        self.temp_end = 0
        self.current_sample = 0

    def __call__(self, x, return_seconds=False):
        """
        x: torch.Tensor
            audio chunk (see examples in repo)

        return_seconds: bool (default - False)
            whether return timestamps in seconds (default - samples)
        """

        if not torch.is_tensor(x):
            x = torch.Tensor(x)

        window_size_samples = len(x[0]) if x.dim() == 2 else len(x)
        self.current_sample += window_size_samples

        speech_prob = self.model(x, self.sampling_rate).item()

        if (speech_prob >= self.threshold) and self.temp_end:
            self.temp_end = 0

        if (speech_prob >= self.threshold) and not self.triggered:
            self.triggered = True
            speech_start = self.current_sample - self.speech_pad_samples
            return {'start': int(speech_start) if not return_seconds else round(speech_start / self.sampling_rate, 1)}

        if (speech_prob < self.threshold - 0.15) and self.triggered:
            if not self.temp_end:
                self.temp_end = self.current_sample
            if self.current_sample - self.temp_end < self.min_silence_samples:
                return None
            else:
                speech_end = self.temp_end + self.speech_pad_samples
                self.temp_end = 0
                self.triggered = False
                return {'end': int(speech_end) if not return_seconds else round(speech_end / self.sampling_rate, 1)}

        return None


class FixedVADIterator(VADIterator):
    '''It fixes VADIterator by allowing to process any audio length, not only exactly 512 frames at once.
    If audio to be processed at once is long and multiple voiced segments detected,
    then __call__ returns the start of the first segment, and end (or middle, which means no end) of the last segment.
    '''

    def reset_states(self):
        super().reset_states()
        self.buffer = np.array([], dtype=np.float32)

    def __call__(self, x, return_seconds=False):
        self.buffer = np.append(self.buffer, x)
        ret = None
        while len(self.buffer) >= 512:
            r = super().__call__(self.buffer[:512], return_seconds=return_seconds)
            self.buffer = self.buffer[512:]
            if ret is None:
                ret = r
            elif r is not None:
                if 'end' in r:
                    ret['end'] = r['end']  # the latter end
                if 'start' in r and 'end' in ret:  # there is an earlier start.
                    # Remove end, merging this segment with the previous one.
                    del ret['end']
        return ret if ret != {} else None

    def process_large_audio(self, x, return_seconds=False):
        segments = []
        buffer = np.array([], dtype=np.float32)
        buffer = np.concatenate([buffer, x])
        offset = 0
        current_segment = None

        while len(buffer) >= 512:
            chunk = buffer[:512]
            result = super().__call__(chunk, return_seconds=False)
            buffer = buffer[512:]

            if result is not None:
                if 'start' in result:
                    if current_segment is None:
                        current_segment = {'start': result['start'] + offset}
                    else:
                        if 'end' in current_segment:
                            segments.append(current_segment)
                            current_segment = {'start': result['start'] + offset}
                if 'end' in result:
                    if current_segment is not None:
                        current_segment['end'] = result['end'] + offset
                        segments.append(current_segment)
                        current_segment = None
            offset += 512

        if current_segment is not None:
            segments.append(current_segment)
        if return_seconds:
            factor = 1 / 512
            for seg in segments:
                seg['start'] *= factor
                if 'end' in seg:
                    seg['end'] *= factor

        return segments if segments else None


def save_audio_segments(audio, sample_rate, segments, output_dir="output_segments"):
    """Сохраняет найденные голосовые сегменты в виде отдельных WAV-файлов."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i, seg in enumerate(segments):
        start_sample = int(seg['start'])
        end_sample = int(seg['end']) if 'end' in seg else len(audio)

        if end_sample - start_sample < 512:  # Фильтруем слишком короткие сегменты
            continue

        segment_audio = audio[start_sample:end_sample]
        file_path = os.path.join(output_dir, f"segment_{i}.wav")

        write(file_path, sample_rate, (segment_audio * 32767).astype(np.int16))
        print(f"Сохранен сегмент: {file_path}")


if __name__ == "__main__":
    # test/demonstrate the need for FixedVADIterator:

    import torch
    model, _ = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad'
    )
    vac = FixedVADIterator(model)
#   vac = VADIterator(model)  # the second case crashes with this

    wav, sr = torchaudio.load("merged_audio.flac")

    if wav.shape[0] > 1:
        wav = torch.mean(wav, dim=0, keepdim=True)  # усредняем каналы до моно

    wav = torchaudio.functional.resample(wav, orig_freq=sr, new_freq=16000)
    audio_buffer = wav.squeeze(0).numpy().astype(np.float32)
    # this works: for both
    # audio_buffer = np.array([0]*(512),dtype=np.float32)
    segments = vac.process_large_audio(audio_buffer)
    print(segments)
    if segments:
        save_audio_segments(audio_buffer, 16000, segments)
        print("Все сегменты сохранены.")
    else:
        print("Голосовые сегменты не найдены.")
    # this crashes on the non FixedVADIterator with
    # ops.prim.RaiseException("Input audio chunk is too short", "builtins.ValueError")
    audio_buffer = np.array([0]*(512-1), dtype=np.float32)
    print(vac(audio_buffer))
