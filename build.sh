#!/bin/sh

set -e
ROOT=$(realpath $(dirname $0))
cd "$ROOT"

# generate gRPC file
python -m grpc_tools.protoc  -I./src/proto --python_out=./src/proto --pyi_out=./src/proto --grpc_python_out=./src/proto stt.proto

#<!--  from proto.grpc import stt_pb2 as stt__pb2  -->
sed -i "s/import stt_pb2 as stt__pb2/import proto.stt_pb2 as stt__pb2/g" "src/proto/stt_pb2_grpc.py"