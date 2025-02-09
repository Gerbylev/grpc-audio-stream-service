#!/bin/bash

ROOT=$(dirname $0)
cd $ROOT

export DOCKER_BUILDKIT=1
docker build . -f Dockerfile-grpc-tools \
              --build-arg USER=$USER \
              --build-arg UID=$(id -u) \
              --build-arg GID=$(id -g) \
              --network=host \
              --no-cache \
              -t grpc-tools

rm -Rf ./src/proto/stt_pb2*

docker run -v $(pwd):/app grpc-tools \
  python -m grpc_tools.protoc  -I./src/proto --python_out=./src/proto --pyi_out=./src/proto --grpc_python_out=./src/proto stt.proto

#<!--  from proto.grpc import stt_pb2 as stt__pb2  -->
sed -i "s/import stt_pb2 as stt__pb2/import proto.stt_pb2 as stt__pb2/g" "src/proto/stt_pb2_grpc.py"

