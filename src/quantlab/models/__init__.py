"""Model wrappers behind a narrow protocol."""

from quantlab.models.base import Model
from quantlab.models.sklearn_models import build_model

__all__ = ["Model", "build_model"]
