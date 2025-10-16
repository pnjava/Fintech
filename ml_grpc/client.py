from __future__ import annotations

import os
from typing import Sequence

import grpc

from ml_grpc import generated as gen


def predict(samples: Sequence[Sequence[float]], host: str | None = None) -> gen.model_pb2.PredictResponse:  # type: ignore[name-defined]
    host = host or os.getenv("GRPC_HOST", "localhost:50051")
    with grpc.insecure_channel(host) as channel:
        stub = gen.model_pb2_grpc.InferenceStub(channel)  # type: ignore[attr-defined]
        req = gen.model_pb2.PredictRequest(  # type: ignore[attr-defined]
            samples=[gen.model_pb2.Sample(features=list(s)) for s in samples]  # type: ignore[attr-defined]
        )
        return stub.Predict(req)


if __name__ == "__main__":
    # 2 sample rows with 32 features each
    rows = [
        [0.0] * 31 + [1.0],
        [0.5] * 32,
    ]
    resp = predict(rows)
    print("scores:", [[round(p, 4) for p in s.prob] for s in resp.scores])

