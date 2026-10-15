"""Focused tests for the interactive Premium key generator."""
from __future__ import annotations

from datetime import date

import pytest

import tools.generate_premium_key as generator
from tools.generate_premium_key import _prompt_duration, _prompt_start, generate_key


def test_generator_prompts_for_start_and_duration():
    today = date(2026, 10, 15)
    answers = iter(("", "3"))
    input_fn = lambda _prompt: next(answers)
    assert _prompt_start(input_fn, today) == today
    assert _prompt_duration(input_fn) == "1ay"


def test_generator_rejects_start_outside_activation_window(tmp_path):
    with pytest.raises(ValueError, match="within two days"):
        generate_key(
            date(2026, 10, 18),
            "1ay",
            tmp_path / "issuer.pem",
            today=date(2026, 10, 15),
        )


def test_generator_rejects_invalid_interactive_dates():
    with pytest.raises(ValueError, match="YYYY-AA-GG"):
        _prompt_start(lambda _prompt: "15.10.2026", date(2026, 10, 15))


def test_generator_resolves_sibling_source_folder(tmp_path, monkeypatch):
    project_parent = tmp_path / "Projeler"
    tool_folder = project_parent / "Paralate Generator"
    source_folder = project_parent / "Paralate-free"
    tool_folder.mkdir(parents=True)
    (source_folder / "licensing").mkdir(parents=True)
    (source_folder / "licensing" / "issue_license.py").write_text(
        "# source marker", encoding="utf-8"
    )
    monkeypatch.setattr(generator, "__file__", str(tool_folder / "generate_premium_key.py"))

    assert generator._project_root() == source_folder
