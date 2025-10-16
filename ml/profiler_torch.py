"""
PyTorch profiler example for CPU/GPU kernels with TensorBoard trace export.
"""
from __future__ import annotations

from pathlib import Path

import torch
from torch import nn


def run_profile(trace_dir: str = "artifacts/traces") -> str:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = nn.Sequential(nn.Linear(32, 128), nn.ReLU(), nn.Linear(128, 2)).to(device)
    x = torch.randn(256, 32, device=device)
    Path(trace_dir).mkdir(parents=True, exist_ok=True)
    trace_path = str(Path(trace_dir) / "torch_trace")

    with torch.profiler.profile(
        activities=[
            torch.profiler.ProfilerActivity.CPU,
            *( [torch.profiler.ProfilerActivity.CUDA] if torch.cuda.is_available() else [] ),
        ],
        on_trace_ready=torch.profiler.tensorboard_trace_handler(trace_path),
        record_shapes=True,
        with_stack=True,
        profile_memory=True,
    ) as prof:
        for _ in range(20):
            y = model(x)
            y.sum().backward()
            prof.step()
    return trace_path


if __name__ == "__main__":
    print(run_profile())

