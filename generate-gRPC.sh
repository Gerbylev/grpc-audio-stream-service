#!/bin/sh

set -e
ROOT=$(realpath $(dirname $0))
cd "$ROOT"

docker build . -f Dockerfile-swagger \
              --build-arg USER=$USER \
              --build-arg UID=$(id -u) \
              --build-arg GID=$(id -g) \
              -t my-openapi-generator

docker run --rm -v "${PWD}":/app my-openapi-generator generate  \
    -i /app/src/spec.yml  -g python-fastapi   -o /app/openapi-generator-output \
    --additional-properties=packageName=cyntai.endpoints --additional-properties=fastapiImplementationPackage=cyntai.endpoints

rm -Rf src/cyntai/endpoints/apis src/cyntai/endpoints/models
mv openapi-generator-output/src/cyntai/endpoints/apis src/cyntai/endpoints/
mv openapi-generator-output/src/cyntai/endpoints/models src/cyntai/endpoints/
mv openapi-generator-output/src/cyntai/endpoints/main.py src/cyntai/endpoints/router_init.py
rm -Rf openapi-generator-output