"""Compatibility facade for project-init AI draft services.

The public import path remains stable while implementation is organized by
contracts, normalization, spreadsheet drafting, and model-call orchestration.
"""

from __future__ import annotations

from . import (
    project_init_ai_contracts as _contracts,
    project_init_ai_normalization as _normalization,
    project_init_ai_pipeline as _pipeline,
    project_init_ai_spreadsheet as _spreadsheet,
)
from .project_init_file_parser import SourceChunk

LLM_TIMEOUT_SECONDS = 90

for _module in (_contracts, _normalization, _spreadsheet, _pipeline):
    for _name in dir(_module):
        if not _name.startswith("__"):
            globals().setdefault(_name, getattr(_module, _name))


def __getattr__(name: str):
    for module in (_contracts, _normalization, _spreadsheet, _pipeline):
        try:
            return getattr(module, name)
        except AttributeError:
            continue
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


del _module
del _name
