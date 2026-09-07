"""Tests for the Nous-Mason-3/4 non-agentic warning detector.

Prior to this check, the warning fired on any model whose name contained
``"mason"`` anywhere (case-insensitive). That false-positived on unrelated
local Modelfiles such as ``mason-brain:qwen3-14b-ctx16k`` — a tool-capable
Qwen3 wrapper that happens to live under the "mason" tag namespace.

``is_nous_mason_non_agentic`` should only match the actual Nous Research
Mason-3 / Mason-4 chat family.
"""

from __future__ import annotations

import pytest

from mason_cli.model_switch import (
    _MASON_MODEL_WARNING,
    _check_mason_model_warning,
    is_nous_mason_non_agentic,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "NousResearch/Mason-3-Llama-3.1-70B",
        "NousResearch/Mason-3-Llama-3.1-405B",
        "mason-3",
        "Mason-3",
        "mason-4",
        "mason-4-405b",
        "mason_4_70b",
        "openrouter/mason3:70b",
        "openrouter/nousresearch/mason-4-405b",
        "NousResearch/Mason3",
        "mason-3.1",
    ],
)
def test_matches_real_nous_mason_chat_models(model_name: str) -> None:
    assert is_nous_mason_non_agentic(model_name), (
        f"expected {model_name!r} to be flagged as Nous Mason 3/4"
    )
    assert _check_mason_model_warning(model_name) == _MASON_MODEL_WARNING


