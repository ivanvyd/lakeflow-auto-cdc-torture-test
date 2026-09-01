# Publishing kit

## Suggested metadata

**Title:** I tried to break Lakeflow AUTO CDC: 18 measured outcomes

**Description:** Nine hostile CDC streams reveal where Lakeflow AUTO CDC handles disorder, needs configuration, or preserves the wrong business state.

**Hero image:** [`media/lakeflow-auto-cdc-torture-test-hero.jpg`](media/lakeflow-auto-cdc-torture-test-hero.jpg)

**Hero alt text:** A stream of CDC events splits into measured handled, ambiguous, and configuration-dependent outcomes.

## LinkedIn post

A green CDC pipeline can still preserve the wrong business state.

I ran nine hostile streams through Lakeflow AUTO CDC: late events, tied sequence values, sparse NULL updates, deletes, replays, SCD2 noise, and bitemporal corrections.

Across 18 configurations:

- 10 handled the input under a complete order
- 3 needed an explicit configuration
- 3 violated the experiment's business rule
- 2 had ambiguous ordering

The most dangerous result completed green. Ordering by ingestion time preserved the wrong state because business time defined “newer.”

The repository includes the generators, pipeline, before-and-after target rows, assertions for all 18 configurations, and a fresh-clone reproduction guide.

Read it and run the experiment: https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test/blob/main/article/article.md

Reply with the CDC failure mode you have seen in production.

## Short post

All 18 Lakeflow AUTO CDC configurations finished green. Three violated the experiment's business rule, and two had ambiguous ordering. I tested late events, tied sequences, NULL updates, deletes, replays, SCD2 noise, and bitemporal history. Code and measured evidence: https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test
