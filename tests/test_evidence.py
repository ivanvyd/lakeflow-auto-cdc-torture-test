import json
from collections import Counter
from pathlib import Path

import pytest
from PIL import Image

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


def test_article_public_assets_and_evidence_language() -> None:
    article = (ROOT / "article/article.md").read_text(encoding="utf-8")
    fact_check = (ROOT / "article/fact-check.md").read_text(encoding="utf-8")
    article_dir = ROOT / "article"
    media_dir = article_dir / "media"
    assert {path.name for path in article_dir.iterdir()} == {
        "article.md",
        "fact-check.md",
        "media",
    }
    assert {path.name for path in media_dir.iterdir()} == {
        "databricks-lockup-full-color.png",
        "lakeflow-auto-cdc-torture-test-hero.png",
        "lakeflow-auto-cdc-torture-test-thumbnail-titled.png",
        "lakeflow-auto-cdc-torture-test-thumbnail.png",
        "source",
        "visual-system.json",
    }
    hero = ROOT / "article/media/lakeflow-auto-cdc-torture-test-hero.png"
    assert hero.stat().st_size > 90_000
    assert "media/lakeflow-auto-cdc-torture-test-hero.png" in article
    assert "silently overwrites" not in article
    assert "bitemporal is the right tool" not in article.lower()
    assert "issues/new" in article
    assert "Five green results I would not ship" in article
    assert "Five still needed intervention before production" in article
    assert "Five green results needed intervention before production" in fact_check
    assert "Prior Community coverage" not in article
    assert "Databricks Community publication audit" not in fact_check
    assert "Originality search" not in fact_check
    assert "raw.githubusercontent.com" in article
    assert "](../" not in article

    public_copy = f"{article}\n{fact_check}".lower()
    for affiliation_term in (
        "client",
        "company",
        "employer",
        "employment",
        "organization",
        "organizational",
    ):
        assert affiliation_term not in public_copy


def test_visual_system_defines_every_outcome_color() -> None:
    style = _json("article/media/visual-system.json")
    assert style["name"] == "Measured Editorial"
    assert style["version"] == 2
    assert style["composition"]["thumbnail"].startswith("Use a 1200x630 crop")
    assert style["brand"]["asset"] == "article/media/databricks-lockup-full-color.png"
    assert style["brand"]["colors"] == {"lava": "#FF3621", "navy": "#0B2026"}
    assert style["outcome_mapping"] == {
        "HANDLED": "teal",
        "CONFIGURATION_DEPENDENT": "ochre",
        "BUSINESS_SEMANTICS": "vermilion",
        "AMBIGUOUS_ORDER": "violet",
    }
    assert all(
        style["palette"][name]["hex"].startswith("#") for name in style["outcome_mapping"].values()
    )


def test_article_thumbnail_uses_the_publication_dimensions() -> None:
    for filename in (
        "lakeflow-auto-cdc-torture-test-thumbnail.png",
        "lakeflow-auto-cdc-torture-test-thumbnail-titled.png",
    ):
        thumbnail = ROOT / "article/media" / filename
        with Image.open(thumbnail) as image:
            assert image.size == (1200, 630)
            assert image.mode == "RGB"


def test_official_databricks_lockup_is_available_for_publication_assets() -> None:
    lockup = ROOT / "article/media/databricks-lockup-full-color.png"
    with Image.open(lockup) as image:
        assert image.size == (200, 31)
        assert image.mode == "RGBA"


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
