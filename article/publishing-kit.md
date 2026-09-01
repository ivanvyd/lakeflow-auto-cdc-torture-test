# Publishing kit

## Suggested metadata

**Title:** I tried to break Lakeflow AUTO CDC. All 18 configurations stayed green.

**Description:** All 18 AUTO CDC configurations stayed green. Five still needed intervention before production. Inspect the measured rows and rerun every case.

**Hero image:** [`media/lakeflow-auto-cdc-torture-test-hero.jpg`](media/lakeflow-auto-cdc-torture-test-hero.jpg)

**Hero alt text:** A stream of CDC events splits into measured handled, ambiguous, and configuration-dependent outcomes.

## LinkedIn post

All 18 Lakeflow AUTO CDC configurations went green. Five still needed intervention before production.

I ran nine hostile streams through Lakeflow AUTO CDC: late events, tied sequence values, sparse NULL updates, deletes, replays, SCD2 noise, and bitemporal corrections.

The measured split:

- 10 handled the input under a complete order
- 3 needed an explicit configuration
- 3 violated the experiment's business rule
- 2 had ambiguous ordering

Scenario 4 ordered by ingestion time, completed green, and preserved `ACTIVE` when business time required `SUSPENDED`.

The repository includes the generators, pipeline, before-and-after target rows, assertions for all 18 configurations, and a fresh-clone reproduction guide.

Read it and run the experiment: https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test/blob/main/article/article.md

Reply with the CDC failure mode you have seen in production.

## Short post

All 18 Lakeflow AUTO CDC configurations finished green. Five still needed intervention before production: three violated the experiment's business rule, and two had ambiguous ordering. Code, target rows, and reproduction guide: https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test

## Five-slide carousel script

### Slide 1

**All 18 AUTO CDC configurations stayed green.**

Five still needed intervention before production.

### Slide 2

**Three green results violated the business rule.**

The wrong clock preserved the wrong state. Default NULL handling replaced an existing value with NULL. Tracking an operational timestamp created 51 SCD2 rows.

### Slide 3

**Two green results had ambiguous order.**

Different business states shared the same sequence value. The documentation does not define which tied payload wins.

### Slide 4

**Fix the source contract and flow.**

Use a composite sequence, define NULL semantics, and exclude operational metadata from history tracking.

### Slide 5

**Run the same failures against your source.**

Nine hostile streams, 18 configurations, captured target rows, and a fresh-clone reproduction guide.

https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test
