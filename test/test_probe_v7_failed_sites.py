# -*- coding: utf-8 -*-

from __future__ import annotations

from examples.probe_v7_failed_sites import ProbeRow, render_markdown


def test_render_markdown_contains_rows():
    row = ProbeRow(
        site="wsj",
        url="https://example.com",
        known_issue="example",
        success=False,
        method="probe_timeout",
        final_url="",
        elapsed_ms=1000.0,
        title="",
        content_length=0,
        error="timed out",
        meta={},
    )

    md = render_markdown([row])
    assert "wsj" in md
    assert "probe_timeout" in md
    assert "timed out" in md
