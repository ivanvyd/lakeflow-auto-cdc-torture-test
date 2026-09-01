All 18 Lakeflow AUTO CDC configurations completed in a green pipeline.

I would not ship five of them.

I ran nine hostile CDC scenarios through AUTO CDC: duplicates, late events, tied sequence values, conflicting clocks, sparse NULL updates, deletes, replays, SCD2 history noise, and bitemporal corrections.

The measured split:

- 10 handled the input under a complete order
- 3 needed an explicit configuration
- 3 violated the experiment's business rule
- 2 had ambiguous ordering

The most dangerous result came from a green pipeline. Ordering by ingestion time preserved `ACTIVE` when the business clock required `SUSPENDED`.

The full article includes the source rows, flow definitions, measured target states, fixes, and a repository you can rerun.

Read the Databricks Community article:

{{DATABRICKS_COMMUNITY_ARTICLE_URL}}

Which CDC failure mode has reached your production system?

#Databricks #DataEngineering
