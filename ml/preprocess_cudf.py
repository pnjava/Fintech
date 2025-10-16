"""
Optional RAPIDS cuDF preprocessing example for tabular data.

Falls back to pandas if cuDF/CUDA is not available.
"""
from __future__ import annotations

import importlib
from typing import Any


def _load_cudf() -> Any | None:
    try:
        return importlib.import_module("cudf")
    except Exception:
        return None


def preprocess(input_csv: str, output_parquet: str) -> None:
    cudf = _load_cudf()
    if cudf is not None:
        df = cudf.read_csv(input_csv)
        # Example feature engineering
        for col in df.columns:
            if df[col].dtype.kind in {"i", "u", "f"}:
                df[f"{col}_z"] = (df[col] - df[col].mean()) / df[col].std()
        df.to_parquet(output_parquet)
        return

    # Fallback to pandas
    import pandas as pd

    df = pd.read_csv(input_csv)
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[f"{col}_z"] = (df[col] - df[col].mean()) / df[col].std(ddof=0)
    df.to_parquet(output_parquet)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    preprocess(args.input, args.output)

