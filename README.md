# Audio Stream Server

Audio Stream Server — это сервис для потокового распознавания речи на Python с gRPC-интерфейсом. В будущем в качестве движка для обработки аудио будет использоваться Whisper.

## Функциональность

- Поддержка потокового распознавания речи через gRPC.
- Гибкие настройки модели, включая параметры аудиоформата, нормализации текста и языковых ограничений.
- Возможность обработки аудиопотоков в реальном времени.

## Технологии

- **Python** — основной язык разработки.
- **gRPC** — протокол взаимодействия для передачи аудиоданных.
- **Whisper** (в будущем) — движок для распознавания речи.

## gRPC API

Определение сервиса `Recognizer`:

```proto
syntax = "proto3";
import "google/protobuf/timestamp.proto";

package cognico.cloud.ai.stt.v1;

service Recognizer {
  rpc RecognizeStreaming (stream StreamingRequest) returns (stream StreamingResponse);
}

message StreamingRequest {
  oneof message {
    StreamingOptions session_options = 1;
    AudioChunk chunk = 2;
  }
}

message StreamingResponse {
  oneof event {
    AlternativeUpdate partial = 1;
    AlternativeUpdate final = 2;
  }
  string session_id = 3;
}
```

## Установка и запуск

### Установка зависимостей

```sh
pip install -r requirements.txt
```

### Генерация gRPC-кода

```sh
./generate-grpc.sh
```

### Запуск сервиса

```sh
python src/main.py
```

## CI/CD и контроль качества кода

- **Pyright** — статический анализатор для проверки типизации.
- **Flake8** — линтер для поддержания единого стиля кода.
- **GitHub Actions** — используется для CI/CD.


*Приветствуются PR и обсуждения!*

