"""Application package for the Fintech platform."""

try:  # pragma: no cover - fallback for environments without optional deps
    from .main import create_application
except ModuleNotFoundError:  # FastAPI may not be installed in some CI runs
    create_application = None  # type: ignore[assignment]
    __all__: list[str] = []
else:
    __all__ = ["create_application"]
