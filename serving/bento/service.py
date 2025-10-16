from __future__ import annotations

import os
from pathlib import Path

import bentoml
import numpy as np
import torch
from bentoml.io import JSON, NumpyNdarray


ARTIFACT_PATH = Path(os.getenv("MODEL_PATH", "artifacts/tinynet.ts"))


def _load_model() -> torch.jit.ScriptModule:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    module = torch.jit.load(str(ARTIFACT_PATH), map_location=device).eval()
    return module.to(device)


svc = bentoml.Service("gpu_inference_service")
model = _load_model()


@svc.api(input=NumpyNdarray(dtype="float32", shape=(None, 32)), output=JSON())
def predict(inputs: np.ndarray) -> dict:
    device = next(model.parameters()).device if hasattr(model, "parameters") else (
        torch.device("cuda" if torch.cuda.is_available() else "cpu")
    )
    x = torch.from_numpy(inputs).to(device)
    with torch.inference_mode():
        y = model(x)
    probs = torch.softmax(y, dim=-1)
    result = probs.detach().cpu().numpy().tolist()
    return {"predictions": result}

