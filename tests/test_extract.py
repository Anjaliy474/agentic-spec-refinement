import json

from reqhq.llm import FakeLLM
from reqhq.orchestrator.extract import extract_frs
from reqhq.prd import prd_from_text, split_sentences


def test_split_sentences_handles_bullets_headings_and_abbreviations():
    text = "# Title\nIntro one. Intro two, e.g. this stays.\n\n- Bullet a\n- Bullet b"
    assert split_sentences(text) == [
        "Title",
        "Intro one.",
        "Intro two, e.g. this stays.",
        "Bullet a",
        "Bullet b",
    ]


def test_extract_frs_keeps_valid_sources_and_drops_empty_items():
    prd = prd_from_text("Users can log in. Users can log out.")
    reply = json.dumps(
        {
            "requirements": [
                {"text": "The system shall let users log in.", "sources": ["s1", "s99"]},
                {"text": "  ", "sources": ["s2"]},
                {"text": "The system shall let users log out.", "sources": ["s2"]},
            ]
        }
    )
    frs = extract_frs(FakeLLM(lambda s, p: reply), prd)
    assert [r.id for r in frs] == ["FR1", "FR2"]
    assert [t.ref for t in frs[0].trace] == ["s1"]
    assert all(r.is_functional for r in frs)
