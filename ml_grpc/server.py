from __future__ import annotations

import os
from concurrent import futures

import grpc as grpc_lib
import numpy as np
import torch

from ml_grpc import generated as gen


MODEL_PATH = os.getenv("MODEL_PATH", "ml/artifacts/tinynet.ts")


def load_model() -> torch.jit.ScriptModule:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    m = torch.jit.load(MODEL_PATH, map_location=device).eval()
    return m.to(device)


class InferenceServicer(gen.model_pb2_grpc.InferenceServicer):
    def __init__(self, model: torch.jit.ScriptModule) -> None:
        self.model = model
        self.device = next(self.model.parameters()).device if hasattr(self.model, "parameters") else (
            torch.device("cuda" if torch.cuda.is_available() else "cpu")
        )

    def Predict(self, request, context):  # type: ignore[override]
        arr = np.array([[*s.features] for s in request.samples], dtype=np.float32)
        x = torch.from_numpy(arr).to(self.device)
        with torch.inference_mode():
            y = self.model(x)
            probs = torch.softmax(y, dim=-1).detach().cpu().numpy()
        resp = gen.model_pb2.PredictResponse(
            scores=[gen.model_pb2.Scores(prob=list(p)) for p in probs]
        )
        return resp


def serve(port: int = 50051) -> None:
    server = grpc_lib.server(futures.ThreadPoolExecutor(max_workers=4))
    model = load_model()
    gen.model_pb2_grpc.add_InferenceServicer_to_server(InferenceServicer(model), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"gRPC Inference server started on :{port}")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()

