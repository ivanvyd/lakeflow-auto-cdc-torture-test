import json
from collections import Counter
from pathlib import Path

import pytest

from src.analysis.write_results import validate_baseline_payload
from src.scenario_specs import TARGET_NAMES

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
    assert "| Handled | 10 |" in article
    assert "| Configuration-dependent | 3 |" in article
    assert "| Business semantics | 3 |" in article
    assert "| Ambiguous order | 2 |" in article


def test_article_publication_assets_and_evidence_language() -> None:
    article = (ROOT / "article/article.md").read_text(encoding="utf-8")
    fact_check = (ROOT / "article/fact-check.md").read_text(encoding="utf-8")
    linkedin = (ROOT / "article/linkedin.md").read_text(encoding="utf-8")
    hero = ROOT / "article/media/lakeflow-auto-cdc-torture-test-hero.jpg"
    assert hero.stat().st_size > 90_000
    assert "media/lakeflow-auto-cdc-torture-test-hero.jpg" in article
    assert "silently overwrites" not in article
    assert "bitemporal is the right tool" not in article.lower()
    assert "issues/new" in article
    assert "Five green results I would not ship" in article
    assert "Prior Community coverage" in article
    assert "from-150-lines-of-merge-into" in article
    assert "Five still needed intervention before production" in article
    assert "Five green results needed intervention before production" in fact_check
    assert "Databricks Technical Blog submission audit" in fact_check
    assert "Publisher eligibility" in fact_check
    assert "{{DATABRICKS_COMMUNITY_ARTICLE_URL}}" in linkedin
    assert "Databricks Community article" in linkedin
    assert not (ROOT / "article/publishing-kit.md").exists()
    assert "raw.githubusercontent.com" in article
    assert "](../" not in article


def test_readme_names_the_checked_in_evidence_fields() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "DOCUMENTED_EXPECTATION" not in readme
    assert "BUSINESS_EXPECTATION" not in readme
    assert "OBSERVED_RESULT" not in readme
    for field in ("ordering_complete", "business_assertion_passed", "expected", "observed"):
        assert f"`{field}`" in readme


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


def test_local_package_does_not_install_managed_spark_runtime() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"pyspark' not in pyproject
    assert '"delta-spark' not in pyproject


def test_make_cleanup_requires_independent_confirmation() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "CONFIRM_SCHEMA ?=" in makefile
    assert "--confirm-schema $(CONFIRM_SCHEMA)" in makefile
    assert "--confirm-schema $(SCHEMA)" not in makefile


def test_baseline_validation_requires_every_registered_target() -> None:
    targets = {target: {} for target in TARGET_NAMES}
    targets.pop("s02_out_of_order_scd2_tgt")
    baseline = {
        "pipeline_id": "pipeline",
        "update_id": "baseline",
        "targets": targets,
    }

    with pytest.raises(ValueError, match="s02_out_of_order_scd2_tgt"):
        validate_baseline_payload(baseline, "pipeline", "late")


def test_baseline_validation_requires_distinct_update_ids() -> None:
    baseline = {
        "pipeline_id": "pipeline",
        "update_id": "same-update",
        "targets": {target: {} for target in TARGET_NAMES},
    }

    with pytest.raises(ValueError, match="must differ"):
        validate_baseline_payload(baseline, "pipeline", "same-update")
