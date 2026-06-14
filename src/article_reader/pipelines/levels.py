# -*- coding: utf-8 -*-
"""Lightweight pipeline level constants."""


class PipelineLevel:
    """Pipeline level identifiers."""

    HTTP = 1
    BASIC_RENDER = 2
    HIGH_PROTECT = 3
    PAYWALL = 4

    @classmethod
    def all_levels(cls) -> list[int]:
        return [cls.HTTP, cls.BASIC_RENDER, cls.HIGH_PROTECT, cls.PAYWALL]

    @classmethod
    def name(cls, level: int) -> str:
        return {
            cls.HTTP: "HTTP",
            cls.BASIC_RENDER: "basic_render",
            cls.HIGH_PROTECT: "high_protect",
            cls.PAYWALL: "paywall",
        }.get(level, f"unknown_pipeline_{level}")
