"""
Minimal PyTorch training example with optional GPU and TorchScript export.

Also demonstrates optional torch.compile and autocast for mixed precision.
Profile with `python ml/profiler_torch.py`.
"""
from __future__ import annotations

import os
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


class TinyNet(nn.Module):
    def __init__(self, in_dim: int = 32, hidden: int = 64, out_dim: int = 2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden), nn.ReLU(), nn.Linear(hidden, out_dim)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # noqa: D401
        return self.net(x)


def train(epochs: int = 5, batch_size: int = 256, out_dir: str = "artifacts") -> dict:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Toy dataset
    N, D, K = 8192, 32, 2
    x = torch.randn(N, D)
    y = (x.sum(dim=1) > 0).long()
    ds = TensorDataset(x, y)
    dl = DataLoader(ds, batch_size=batch_size, shuffle=True, num_workers=0)

    model = TinyNet(D, 64, K).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()

    scaler = torch.cuda.amp.GradScaler(enabled=torch.cuda.is_available())

    model.train()
    for epoch in range(epochs):
        running = 0.0
        for xb, yb in dl:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                logits = model(xb)
                loss = loss_fn(logits, yb)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            running += loss.item() * xb.size(0)
        print(f"epoch={epoch+1} loss={running/len(ds):.4f}")

    # Export TorchScript
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    scripted = torch.jit.script(model.cpu().eval())
    ts_path = out / "tinynet.ts"
    scripted.save(str(ts_path))
    return {"torchscript": str(ts_path)}


if __name__ == "__main__":
    epochs = int(os.getenv("EPOCHS", "5"))
    print(train(epochs=epochs))

