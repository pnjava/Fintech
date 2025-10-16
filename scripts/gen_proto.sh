#!/usr/bin/env bash
set -euo pipefail
PROTO=${1:-ml_grpc/model.proto}
OUT=${2:-ml_grpc/generated}

python -m grpc_tools.protoc \
  -I. \
  --python_out="$OUT" \
  --grpc_python_out="$OUT" \
  "$PROTO"

echo "Generated stubs in $OUT"
