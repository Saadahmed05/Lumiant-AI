"""Terminology layer: Arabic normalisation, ERP and Arabic hints, glossary notes (meanings only, never figures)."""

from __future__ import annotations

import re

import pytest

from lumiant.agent.providers import parse_days
from lumiant.agent.terminology import CONCEPTS, ascii_digits, expand, glossary_note, normalize


def test_normalize_unifies_arabic_spelling_variants() -> None:
    assert normalize("أإآٱ") == "اااا"
    assert normalize("مستشفى") == normalize("مستشفي")
    assert normalize("قيمة") == "قيمه"
    assert normalize("المَخْزُون") == "المخزون"  # diacritics
    assert normalize("المـــخزون") == "المخزون"  # tatweel
    assert normalize("كم؟") == "كم?"


def test_arabic_indic_and_persian_digits_become_ascii() -> None:
    assert ascii_digits("١٢٣٤٥٦٧٨٩٠") == "1234567890"
    assert ascii_digits("۱۲۳") == "123"


@pytest.mark.parametrize(
    ("question", "hint"),
    [
        ("Show stock by plant", "warehouse"),
        ("Show on-hand by subinventory", "storage location"),
        ("Value by material group", "item group"),
        ("Which items are below the reorder point?", "below reorder level"),
        ("Items above their reordering rule maximum", "excess stock"),
        ("Dead stock with no goods issue", "not moved"),
        ("Batches past VFDAT", "expiry"),
        ("Show the valuation", "inventory value"),
        ("كم قيمة المخزون؟", "how much inventory do we have"),
        ("اعرض المخزون حسب المستودع", "by"),
        ("ما الأصناف الراكدة؟", "not moved"),
        ("ما المواد التي تحتاج إلى تخزين خاص؟", "special storage"),
        ("أصناف الفئة ب", "b-category items"),
    ],
)
def test_expand_adds_canonical_hints(question: str, hint: str) -> None:
    hints = expand(question).split(" :: ", 1)[1].split("; ")
    assert hint in hints


def test_expand_keeps_the_original_words_first_and_adds_nothing_to_plain_questions() -> None:
    assert expand("Which items are below reorder level?") == "which items are below reorder level?"
    assert expand("Show STOCK by Plant").startswith("show stock by plant :: ")


@pytest.mark.parametrize(
    ("question", "days"),
    [("منذ ستة أشهر", 180), ("خلال شهرين", 60), ("خلال ٣٠ يوما", 30), ("منذ أسبوعين", 14), ("خلال سنة", 365)],
)
def test_arabic_durations_reach_parse_days(question: str, days: int) -> None:
    assert parse_days(expand(question), 0) == days


def test_item_code_hint_depends_on_a_code() -> None:
    assert "how much stock of item" in expand("كم المخزون من الصنف ١٠٠٠٤٥٦")
    assert "how much inventory do we have" in expand("كم المخزون لدينا؟")


def test_glossary_note_names_concepts_and_systems_but_no_figures() -> None:
    note = glossary_note("Show unrestricted stock by plant and subinventory")
    assert "SAP plant (WERKS)" in note
    assert "subinventory" in note
    assert glossary_note("What is the weather in Paris?") == ""
    for c in CONCEPTS:  # meanings only: no quantities, prices or currency in the vocabulary
        assert not re.search(r"\d{2,}|USD|EUR|SAR|GBP", c.meaning), c.key
