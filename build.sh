#!/bin/sh

set -e
ROOT=$(realpath $(dirname $0))
cd "$ROOT"

if [ -z "$1" ]; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
else
    BRANCH=$1
fi

#     GENERATE gRPC
sh generate-grpc.sh

#     RUN TESTS
docker build . -f Dockerfile-test \
               --build-arg USER=$USER \
               --build-arg UID=$(id -u) \
               --build-arg GID=$(id -g) \
               -t docker-stt-test

docker run --rm -v $(pwd):/app -w /app/tests docker-stt-test pytest


if [ $? -ne 0 ]; then
  echo "Тесты не прошли. Остановка сборки."
  exit 1  # Останавливаем сборку с ошибкой
else
  echo "Тесты прошли успешно."
fi

#     BUILD PRODUCTION IMAGE
SERVICE_NAME="cognico-stt"
BRANCH_NAME_LOWER=$(echo "$BRANCH" | tr '[:upper:]' '[:lower:]')

IMAGE=raghtnes/$SERVICE_NAME:$BRANCH_NAME_LOWER

DOCKER_BUILDKIT=1 docker build . -t $IMAGE
docker push $IMAGE

echo "$IMAGE"

