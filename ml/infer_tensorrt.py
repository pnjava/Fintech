"""
TensorRT inference example from TorchScript.

Requires TensorRT or torch_tensorrt; falls back to plain PyTorch if unavailable.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import torch


def _load_torch_tensorrt():
    try:
        return importlib.import_module("torch_tensorrt")
    except Exception:
        return None


def load_torchscript(ts_path: str) -> torch.jit.ScriptModule:
    return torch.jit.load(ts_path, map_location="cuda" if torch.cuda.is_available() else "cpu").eval()


def infer(ts_path: str, batch: int = 32) -> dict:
    module = load_torchscript(ts_path)

    # Try to compile via torch_tensorrt if available
    trt = _load_torch_tensorrt()
    if trt and torch.cuda.is_available():
        try:
            compiled = trt.compile(
                module,
                inputs=[trt.Input(min_shape=(1, 32), opt_shape=(batch, 32), max_shape=(1024, 32))],
                enabled_precisions={torch.float16},
            )
            engine = compiled
        except Exception:
            engine = module
    else:
        engine = module

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    x = torch.randn(batch, 32, device=device)
    with torch.inference_mode():
        y = engine(x)
    return {"batch": batch, "mean": float(y.mean().detach().cpu().item())}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--ts", default="artifacts/tinynet.ts")
    parser.add_argument("--batch", type=int, default=32)
    args = parser.parse_args()
    print(infer(args.ts, args.batch))

