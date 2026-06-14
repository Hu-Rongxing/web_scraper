# -*- coding: utf-8 -*-
"""Shared output paths for integration test artifacts."""

from __future__ import annotations

from pathlib import Path


def output_path(filename: str) -> Path:
    """Return a path under test/output and ensure the directory exists."""
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    return output_dir / filename
