# Databricks Community publishing kit

This package is for the Databricks Community [Community Articles](https://community.databricks.com/t5/community-articles/bd-p/Knowledge-Sharing-Hub) section. Databricks' [submission announcement](https://community.databricks.com/t5/announcements/share-your-expertise-submit-your-blogs-and-videos-to-the/m-p/71752/highlight/true) directs technical contributors to post their findings there for review.

## Submission fields

**Title:** I tried to break Lakeflow AUTO CDC: 18 green configurations, 5 I wouldn't ship

**Teaser:** Every configuration completed in a green pipeline. Three produced the wrong business state, and two left ordering ambiguous. Here are the target rows, fixes, and a reproducible test suite.

**Suggested labels:** `Data Engineering`, `Databricks Lakeflow`, `CDC`, `Delta Lake`

Use only labels offered by the Community editor. The first three are the most specific choices if the editor limits the number of labels.

## Hero image

**File:** [`lakeflow-auto-cdc-torture-test-hero.jpg`](media/lakeflow-auto-cdc-torture-test-hero.jpg)

**Direct URL:** https://raw.githubusercontent.com/ivanvyd/lakeflow-auto-cdc-torture-test/main/article/media/lakeflow-auto-cdc-torture-test-hero.jpg

**Alt text:** A stream of CDC events splits into measured handled, ambiguous, and configuration-dependent outcomes.

Upload the image through the Community editor rather than relying on the direct URL. This gives the post a Community-hosted thumbnail and avoids third-party image loading failures.

## Opening preview

All 18 Lakeflow AUTO CDC configurations completed in a green pipeline. I still would not ship five of them.

I tested duplicates, late events, tied sequence values, conflicting clocks, sparse NULL updates, deletes, full replays, SCD2 history noise, and bitemporal corrections. Three configurations violated the experiment's business rule. Two used incomplete ordering. The repository includes the generators, flow definitions, before-and-after target rows, assertions, and a fresh-clone reproduction guide.

The most dangerous result was not a failed pipeline. It was a green pipeline ordered by ingestion time that preserved `ACTIVE` when the business clock required `SUSPENDED`.

## Article body

Use [`article.md`](article.md) as the canonical body. When the Community editor has a separate title field, paste from the hero image onward and omit the Markdown H1.

The article uses absolute public URLs for figures, code, evidence, and official Databricks documentation so its links remain valid outside GitHub. For the best presentation, upload all four figures through the Community editor and retain their existing alt text:

1. `results/figures/wrong_clock.png`
2. `results/figures/scd2_history_noise.png`
3. `results/figures/bitemporal_timeline.png`
4. `results/figures/summary_matrix.png`

## Closing discussion prompt

Which CDC failure mode has reached production in your system: the wrong clock, a tied sequence, ambiguous NULL semantics, noisy SCD2 history, or something this suite does not cover? If you can reduce it to source rows plus an expected target, open an issue and I will turn it into a reproducible scenario.

## Final editor check

- Keep the independent-experiment disclosure near the top.
- Preserve the word **Beta** everywhere bitemporal AUTO CDC is discussed.
- Keep measured results labeled as measured; do not recast them as universal platform guarantees.
- Verify the hero and four result figures render at desktop and mobile widths.
- Verify the repository, evidence ledger, official documentation, and issue links open in a signed-out browser.
- Preview code blocks, tables, and alt text before requesting publication.
- Do not add claims about throughput, scale, schema evolution, or multi-stream joins; those were not tested.

The repository is public and reproducible: https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test
