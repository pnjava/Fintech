GPU ML pipeline components for training, optimization, and inference.

Contents
- preprocess_cudf.py: Optional RAPIDS cuDF preprocessing example.
- train_pytorch.py: PyTorch model training with optional GPU.
- train_xgboost.py: XGBoost GPU training example.
- infer_tensorrt.py: TensorRT inference path from a TorchScript/ONNX model.
- profiler_torch.py: PyTorch profiler usage for bottleneck analysis.

Notes
- All scripts are safe to run on CPU-only machines; they auto-detect CUDA.
- For RAPIDS and TensorRT, ensure appropriate CUDA drivers and packages.

