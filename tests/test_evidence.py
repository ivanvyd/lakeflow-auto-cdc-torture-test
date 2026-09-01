import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _json(relative_path: str):
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_published_matrix_matches_article_summary() -> None:
    matrix = _json("results/normalized/summary_matrix.json")
    assert len(matrix) == 18
    assert {row["pipeline"] for row in matrix} == {"GREEN"}
    assert Counter(row["classification"] for row in matrix) == {
        "HANDLED": 10,
        "CONFIGURATION_DEPENDENT": 3,
        "BUSINESS_SEMANTICS": 3,
        "AMBIGUOUS_ORDER": 2,
    }
    article = (ROOT / "article/article.md").read_text(encoding="utf-8")
    assert "**ten** `HANDLED`" in article
    assert "**three** `CONFIGURATION_DEPENDENT`" in article
    assert "**three** `BUSINESS_SEMANTICS`" in article
    assert "**two** `AMBIGUOUS_ORDER`" in article


def test_two_phase_evidence_covers_every_configuration() -> None:
    matrix = _json("results/normalized/summary_matrix.json")
    state = _json("results/raw/target_state.json")
    baseline = state["baseline"]
    after = state["after_late_phase"]
    configurations = {row["configuration"] for row in matrix}
    assert set(baseline) == configurations
    assert set(after) == configurations
    assert state["baseline_update_id"] != state["late_phase_update_id"]
    changed = {name for name in configurations if baseline[name] != after[name]}
    assert changed == {
        "s02_out_of_order_scd2_tgt",
        "s06_delete_late_scd2_tgt",
    }


def test_raw_results_use_current_evidence_schema() -> None:
    rows = _json("results/raw/scenario_results.json")
    assert len(rows) == 18
    assert all("ordering_complete" in row for row in rows)
    assert all("documented_contract_valid" not in row for row in rows)
