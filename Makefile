PYTHON ?= python
DATABRICKS ?= databricks
PROFILE ?= DEFAULT
BUNDLE_TARGET ?= dev
CATALOG ?= workspace
SCHEMA ?= auto_cdc_torture_test

DATABRICKS_FLAGS := --profile $(PROFILE)
BUNDLE_FLAGS := -t $(BUNDLE_TARGET) $(DATABRICKS_FLAGS) --var="catalog=$(CATALOG)" --var="schema=$(SCHEMA)"

.PHONY: help
help:
	@echo "Targets:"
	@echo "  make setup    - Validate and deploy the Databricks bundle."
	@echo "  make test     - Run the initial and late/replay phases, then verify live targets."
	@echo "  make results  - Normalize results, build summary matrix and figures."
	@echo "  make cleanup  - Drop schema and destroy the bundle."

.PHONY: setup
setup: bundle_setup

.PHONY: bundle_setup
bundle_setup:
	$(DATABRICKS) bundle validate $(BUNDLE_FLAGS)
	$(DATABRICKS) bundle deploy $(BUNDLE_FLAGS)

.PHONY: run_full_refresh
run_full_refresh:
	$(DATABRICKS) bundle run auto_cdc_torture_pipeline --full-refresh-all $(BUNDLE_FLAGS)

.PHONY: run_incremental
run_incremental:
	$(DATABRICKS) bundle run auto_cdc_torture_pipeline $(BUNDLE_FLAGS)

.PHONY: generate_all
generate_all:
	$(PYTHON) -m src.generators.apply_to_workspace --profile $(PROFILE) --catalog $(CATALOG) --schema $(SCHEMA) --phase initial

.PHONY: append_late
append_late:
	$(PYTHON) -m src.generators.apply_to_workspace --profile $(PROFILE) --catalog $(CATALOG) --schema $(SCHEMA) --phase late

.PHONY: generate_one
generate_one:
	@if [ -z "$(SCENARIO)" ]; then echo "Usage: make generate_one SCENARIO=01_duplicate"; exit 1; fi
	$(PYTHON) -m src.generators.apply_to_workspace --profile $(PROFILE) --catalog $(CATALOG) --schema $(SCHEMA) --scenario $(SCENARIO) --phase initial

.PHONY: capture_baseline
capture_baseline:
	@pipeline_id=$$($(DATABRICKS) bundle summary $(BUNDLE_FLAGS) -o json | jq -r '.resources.pipelines.auto_cdc_torture_pipeline.id'); \
	update_id=$$($(DATABRICKS) pipelines list-updates $$pipeline_id $(DATABRICKS_FLAGS) --max-results 1 -o json | jq -r '.updates[0].update_id'); \
	$(PYTHON) -m src.analysis.capture_baseline --profile $(PROFILE) --catalog $(CATALOG) --schema $(SCHEMA) --pipeline-id $$pipeline_id --update-id $$update_id

.PHONY: assert_all
assert_all:
	@pipeline_id=$$($(DATABRICKS) bundle summary $(BUNDLE_FLAGS) -o json | jq -r '.resources.pipelines.auto_cdc_torture_pipeline.id'); \
	update_id=$$($(DATABRICKS) pipelines list-updates $$pipeline_id $(DATABRICKS_FLAGS) --max-results 1 -o json | jq -r '.updates[0].update_id'); \
	$(PYTHON) -m src.analysis.write_results --profile $(PROFILE) --catalog $(CATALOG) --schema $(SCHEMA) --pipeline-id $$pipeline_id --update-id $$update_id

.PHONY: test
test: generate_all run_full_refresh capture_baseline append_late run_incremental assert_all normalize

.PHONY: normalize
normalize:
	$(PYTHON) -m src.analysis.normalize --profile $(PROFILE) --catalog $(CATALOG) --schema $(SCHEMA)

.PHONY: results
results: normalize
	$(PYTHON) -m src.analysis.figures

.PHONY: cleanup
cleanup:
	$(DATABRICKS) bundle destroy --auto-approve $(BUNDLE_FLAGS)
	$(PYTHON) -m src.analysis.cleanup --profile $(PROFILE) --catalog $(CATALOG) --schema $(SCHEMA) --confirm-schema $(SCHEMA)
