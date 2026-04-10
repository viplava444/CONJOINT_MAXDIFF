"""
core/__init__.py
Public surface of the core package.
"""

from .models import (
    Attribute,
    CBCInput,
    CBCDesign,
    CBCTask,
    MaxDiffInput,
    MaxDiffDesign,
    MaxDiffSet,
    Prohibition,
    DiagnosticsReport,
)
from .cbc_generator import generate_cbc_design
from .maxdiff_generator import generate_maxdiff_design
from .validator import validate_cbc, validate_maxdiff

__all__ = [
    "Attribute", "CBCInput", "CBCDesign", "CBCTask",
    "MaxDiffInput", "MaxDiffDesign", "MaxDiffSet", "Prohibition",
    "DiagnosticsReport",
    "generate_cbc_design", "generate_maxdiff_design",
    "validate_cbc", "validate_maxdiff",
]
