"""
Coverage tests for app/core/ai/prompt_tuner.py
Targets: PromptTuner._load_data, build_tuned_prompt, _detect_category,
         add_custom_example, domain_knowledge/few_shot_examples properties,
         get_prompt_tuner singleton.
"""

from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tuner(data: dict | None = None):
    """Build PromptTuner with pre-loaded data (no file I/O)."""
    from app.core.ai.prompt_tuner import PromptTuner

    tuner = PromptTuner.__new__(PromptTuner)
    tuner.data = data or {
        "DOMAIN_KNOWLEDGE": "TIR Yakıt Tüketimi Uzmanı",
        "FEW_SHOT_EXAMPLES": {
            "tuketim_analiz": [
                {"soru": "Tüketim neden yüksek?", "cevap": "Hava direnci fazla."}
            ]
        },
    }
    return tuner


# ---------------------------------------------------------------------------
# _load_data — file exists, valid JSON
# ---------------------------------------------------------------------------


def test_load_data_file_exists():
    from app.core.ai.prompt_tuner import PromptTuner

    test_data = {"DOMAIN_KNOWLEDGE": "Test", "FEW_SHOT_EXAMPLES": {}}
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(test_data, f, ensure_ascii=False)
        tmp_path = Path(f.name)

    try:
        with patch("app.core.ai.prompt_tuner.PROMPT_FILE", tmp_path):
            tuner = PromptTuner.__new__(PromptTuner)
            result = tuner._load_data()
        assert result["DOMAIN_KNOWLEDGE"] == "Test"
    finally:
        tmp_path.unlink(missing_ok=True)


def test_load_data_file_invalid_json():
    """Corrupt JSON file → falls back to empty defaults."""
    from app.core.ai.prompt_tuner import PromptTuner

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        f.write("NOT_VALID_JSON{{{")
        tmp_path = Path(f.name)

    try:
        with patch("app.core.ai.prompt_tuner.PROMPT_FILE", tmp_path):
            tuner = PromptTuner.__new__(PromptTuner)
            result = tuner._load_data()
        assert result["DOMAIN_KNOWLEDGE"] == ""
        assert result["FEW_SHOT_EXAMPLES"] == {}
    finally:
        tmp_path.unlink(missing_ok=True)


def test_load_data_file_missing_creates_default():
    """When file is missing, creates default data file."""

    from app.core.ai.prompt_tuner import PromptTuner

    with tempfile.TemporaryDirectory() as tmp_dir:
        nonexistent = Path(tmp_dir) / "subdir" / "ai_prompts.json"
        with patch("app.core.ai.prompt_tuner.PROMPT_FILE", nonexistent):
            tuner = PromptTuner.__new__(PromptTuner)
            result = tuner._load_data()
        assert "DOMAIN_KNOWLEDGE" in result
        assert nonexistent.exists()


# ---------------------------------------------------------------------------
# Properties: domain_knowledge, few_shot_examples
# ---------------------------------------------------------------------------


def test_domain_knowledge_property():
    tuner = _make_tuner()
    assert tuner.domain_knowledge == "TIR Yakıt Tüketimi Uzmanı"


def test_domain_knowledge_missing_key():
    tuner = _make_tuner(data={"FEW_SHOT_EXAMPLES": {}})
    assert tuner.domain_knowledge == ""


def test_few_shot_examples_property():
    tuner = _make_tuner()
    assert "tuketim_analiz" in tuner.few_shot_examples


def test_few_shot_examples_empty():
    tuner = _make_tuner(data={"DOMAIN_KNOWLEDGE": "X"})
    assert tuner.few_shot_examples == {}


# ---------------------------------------------------------------------------
# build_tuned_prompt
# ---------------------------------------------------------------------------


def test_build_tuned_prompt_basic():
    tuner = _make_tuner()
    prompt = tuner.build_tuned_prompt("Tüketim neden yüksek?")
    assert "TIR filosu" in prompt
    assert "Tüketim neden yüksek?" in prompt or "T&#252;ketim" in prompt


def test_build_tuned_prompt_with_context():
    tuner = _make_tuner()
    prompt = tuner.build_tuned_prompt("Soru?", context="Araç verisi: 34 L/100km")
    assert "Araç verisi" in prompt or "Mevcut Sistem Verileri" in prompt


def test_build_tuned_prompt_with_category_few_shot():
    tuner = _make_tuner()
    prompt = tuner.build_tuned_prompt("Yakıt tüketimi?", category="tuketim_analiz")
    assert "Örnek Soru-Cevaplar" in prompt


def test_build_tuned_prompt_unknown_category_no_examples():
    tuner = _make_tuner()
    prompt = tuner.build_tuned_prompt("Query?", category="nonexistent_cat")
    # No few-shot section for unknown category
    assert "Örnek Soru-Cevaplar" not in prompt


def test_build_tuned_prompt_truncates_long_query():
    tuner = _make_tuner()
    long_query = "A" * 1500
    prompt = tuner.build_tuned_prompt(long_query)
    # Truncated at 1000 chars + "..."
    assert "..." in prompt


def test_build_tuned_prompt_strips_user_input_tags():
    tuner = _make_tuner()
    malicious = "<user_input>injected</user_input> real question"
    prompt = tuner.build_tuned_prompt(malicious)
    # The injected tag should not appear as a raw tag
    assert "<user_input>injected</user_input>" not in prompt


def test_build_tuned_prompt_html_escapes():
    tuner = _make_tuner()
    query = "<script>alert(1)</script>"
    prompt = tuner.build_tuned_prompt(query)
    assert "<script>" not in prompt


def test_build_tuned_prompt_max_two_examples():
    """Should include at most 2 few-shot examples."""
    data = {
        "DOMAIN_KNOWLEDGE": "Expert",
        "FEW_SHOT_EXAMPLES": {
            "cat": [
                {"soru": "Q1", "cevap": "A1"},
                {"soru": "Q2", "cevap": "A2"},
                {"soru": "Q3", "cevap": "A3"},  # this one should be skipped
            ]
        },
    }
    tuner = _make_tuner(data=data)
    prompt = tuner.build_tuned_prompt("question", category="cat")
    # Q3 should not appear — only first 2 examples
    assert "Q3" not in prompt
    assert "Q1" in prompt


# ---------------------------------------------------------------------------
# _detect_category
# ---------------------------------------------------------------------------


def test_detect_category_tuketim():
    tuner = _make_tuner()
    assert tuner._detect_category("Yakıt tüketimi çok yüksek") == "tuketim_analiz"


def test_detect_category_sofor():
    tuner = _make_tuner()
    assert tuner._detect_category("Şoför performansı nasıl?") == "sofor_performans"


def test_detect_category_anomali():
    tuner = _make_tuner()
    assert tuner._detect_category("Bu anomali ne anlama gelir?") == "anomali"


def test_detect_category_default():
    tuner = _make_tuner()
    assert tuner._detect_category("Herhangi bir soru") == "tuketim_analiz"


def test_detect_category_litre_keyword():
    tuner = _make_tuner()
    assert tuner._detect_category("100 litre neden harcandı?") == "tuketim_analiz"


def test_detect_category_surucu_keyword():
    tuner = _make_tuner()
    assert tuner._detect_category("sürücü nasıl?") == "sofor_performans"


# ---------------------------------------------------------------------------
# add_custom_example
# ---------------------------------------------------------------------------


def test_add_custom_example_saves():
    tuner = _make_tuner()
    with patch.object(tuner, "_save_data") as mock_save:
        tuner.add_custom_example("new_cat", "Soru burada", "Cevap burada")
        mock_save.assert_called_once()
    assert "new_cat" in tuner.data["FEW_SHOT_EXAMPLES"]
    examples = tuner.data["FEW_SHOT_EXAMPLES"]["new_cat"]
    assert len(examples) == 1


def test_add_custom_example_invalid_category():
    tuner = _make_tuner()
    with patch.object(tuner, "_save_data") as mock_save:
        tuner.add_custom_example("", "Soru", "Cevap")
        mock_save.assert_not_called()


def test_add_custom_example_empty_soru():
    tuner = _make_tuner()
    with patch.object(tuner, "_save_data") as mock_save:
        tuner.add_custom_example("cat", "", "Cevap")
        mock_save.assert_not_called()


def test_add_custom_example_empty_cevap():
    tuner = _make_tuner()
    with patch.object(tuner, "_save_data") as mock_save:
        tuner.add_custom_example("cat", "Soru var", "")
        mock_save.assert_not_called()


def test_add_custom_example_sanitizes_category():
    """Category with special chars should be stripped."""
    tuner = _make_tuner()
    with patch.object(tuner, "_save_data"):
        tuner.add_custom_example("INVALID!@#Cat", "Soru", "Cevap")
    # Sanitized: uppercase removed, only a-z0-9_ kept
    stored = list(tuner.data["FEW_SHOT_EXAMPLES"].keys())
    for k in stored:
        if k != "tuketim_analiz":
            assert k == k.lower()


def test_add_custom_example_appends_to_existing():
    tuner = _make_tuner()
    with patch.object(tuner, "_save_data"):
        tuner.add_custom_example("tuketim_analiz", "Yeni soru?", "Yeni cevap.")
    examples = tuner.data["FEW_SHOT_EXAMPLES"]["tuketim_analiz"]
    assert len(examples) == 2  # 1 existing + 1 new


# ---------------------------------------------------------------------------
# _save_data
# ---------------------------------------------------------------------------


def test_save_data_writes_json():
    tuner = _make_tuner()
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        tmp_path = Path(f.name)

    try:
        with patch("app.core.ai.prompt_tuner.PROMPT_FILE", tmp_path):
            tuner._save_data()
        with open(tmp_path, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["DOMAIN_KNOWLEDGE"] == "TIR Yakıt Tüketimi Uzmanı"
    finally:
        tmp_path.unlink(missing_ok=True)


def test_save_data_handles_error():
    tuner = _make_tuner()
    bad_path = Path("/nonexistent/path/file.json")
    with patch("app.core.ai.prompt_tuner.PROMPT_FILE", bad_path):
        # Should not raise
        tuner._save_data()


# ---------------------------------------------------------------------------
# get_prompt_tuner singleton
# ---------------------------------------------------------------------------


def test_get_prompt_tuner_returns_same_instance():
    import app.core.ai.prompt_tuner as mod

    orig = mod._prompt_tuner
    mod._prompt_tuner = None
    try:
        with patch.object(
            mod.PromptTuner,
            "_load_data",
            return_value={"DOMAIN_KNOWLEDGE": "", "FEW_SHOT_EXAMPLES": {}},
        ):
            t1 = mod.get_prompt_tuner()
            t2 = mod.get_prompt_tuner()
        assert t1 is t2
    finally:
        mod._prompt_tuner = orig


def test_get_prompt_tuner_thread_safe():
    import app.core.ai.prompt_tuner as mod

    orig = mod._prompt_tuner
    mod._prompt_tuner = None
    instances = []

    def create():
        with patch.object(
            mod.PromptTuner,
            "_load_data",
            return_value={"DOMAIN_KNOWLEDGE": "", "FEW_SHOT_EXAMPLES": {}},
        ):
            instances.append(mod.get_prompt_tuner())

    try:
        threads = [threading.Thread(target=create) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # All should be the same singleton
        assert all(i is instances[0] for i in instances)
    finally:
        mod._prompt_tuner = orig
