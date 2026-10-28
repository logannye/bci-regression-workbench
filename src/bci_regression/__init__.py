"""Compare existing decoder predictions without running the models."""

__version__ = "0.1.0"

from .core import EvaluationSet, PredictionSet, compare, reproduce

__all__ = ["EvaluationSet", "PredictionSet", "compare", "reproduce", "__version__"]
