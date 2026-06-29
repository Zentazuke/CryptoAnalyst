"""Test the model-card cell formatter (pure)."""
from scripts.model_card import _fmt


def test_fmt_none():
    assert _fmt(None) == "—"
    assert _fmt({"hit_rate": None}) == "—"


def test_fmt_edge_cell():
    cell = _fmt({"hit_rate": 0.66, "base_rate": 0.50, "lift": 1.32,
                 "ci_low": 0.56, "ci_high": 0.74, "verdict": "edge", "n": 96})
    assert "66%" in cell and "[56–74]" in cell and "vs 50%" in cell
    assert "1.32" in cell and "EDGE" in cell and "n=96" in cell


def test_fmt_uses_count_when_no_n():
    cell = _fmt({"hit_rate": 0.5, "base_rate": 0.5, "lift": 1.0,
                 "ci_low": 0.45, "ci_high": 0.55, "verdict": "no-edge", "count": 1200})
    assert "n=1200" in cell and "no edge" in cell
