"""
XGBoost GPU training example. Falls back to CPU if no GPU.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xgboost as xgb


def train(out_dir: str = "artifacts") -> dict:
    rng = np.random.default_rng(42)
    n, d = 5000, 40
    X = rng.standard_normal(size=(n, d)).astype(np.float32)
    y = (X.sum(axis=1) > 0).astype(np.int32)

    dtrain = xgb.DMatrix(X, label=y)
    params = {
        "max_depth": 5,
        "eta": 0.1,
        "objective": "binary:logistic",
        "tree_method": "gpu_hist" if xgb.context().has_cuda_device else "hist",
    }
    bst = xgb.train(params, dtrain, num_boost_round=100)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    model_path = out / "xgb_model.json"
    bst.save_model(str(model_path))
    return {"xgboost_model": str(model_path)}


if __name__ == "__main__":
    print(json.dumps(train()))

