# Summary matrix

| Scenario | Configuration | Pipeline | Correct state | Ordering | Classification | target rows | history rows |
|---|---|---|---|---|---|---|---|
| 01_duplicate | s01_duplicate_tgt | GREEN | YES | COMPLETE | HANDLED | 1 | 0 |
| 01_duplicate_replay | s01_duplicate_replay_tgt | GREEN | YES | COMPLETE | HANDLED | 1 | 0 |
| 02_out_of_order | s02_out_of_order_tgt | GREEN | YES | COMPLETE | HANDLED | 1 | 0 |
| 02_out_of_order_scd2 | s02_out_of_order_scd2_tgt | GREEN | YES | COMPLETE | HANDLED | 2 | 2 |
| 03_seq_collision_a | s03_seq_collision_a_tgt | GREEN | NO | AMBIGUOUS | AMBIGUOUS_ORDER | 1 | 0 |
| 03_seq_collision_b | s03_seq_collision_b_tgt | GREEN | YES | AMBIGUOUS | AMBIGUOUS_ORDER | 1 | 0 |
| 03_seq_collision_b_struct | s03_seq_collision_b_struct_tgt | GREEN | YES | COMPLETE | HANDLED | 1 | 0 |
| 04_wrong_clock_ingest | s04_wrong_clock_ingest_tgt | GREEN | NO | COMPLETE | BUSINESS_SEMANTICS | 1 | 0 |
| 04_wrong_clock_source | s04_wrong_clock_source_tgt | GREEN | YES | COMPLETE | CONFIGURATION_DEPENDENT | 1 | 0 |
| 05_sparse_a | s05_sparse_a_tgt | GREEN | NO | COMPLETE | BUSINESS_SEMANTICS | 1 | 0 |
| 05_sparse_b | s05_sparse_b_tgt | GREEN | YES | COMPLETE | CONFIGURATION_DEPENDENT | 1 | 0 |
| 06_delete_late_scd1 | s06_delete_late_tgt | GREEN | YES | COMPLETE | HANDLED | 0 | 0 |
| 06_delete_late_scd2 | s06_delete_late_scd2_tgt | GREEN | YES | COMPLETE | HANDLED | 2 | 2 |
| 07_replay_scd1 | s07_replay_tgt | GREEN | YES | COMPLETE | HANDLED | 0 | 0 |
| 07_replay_scd2 | s07_replay_scd2_tgt | GREEN | YES | COMPLETE | HANDLED | 4 | 4 |
| 08_history_a | s08_history_a_scd2_tgt | GREEN | NO | COMPLETE | BUSINESS_SEMANTICS | 51 | 51 |
| 08_history_b | s08_history_b_scd2_tgt | GREEN | YES | COMPLETE | CONFIGURATION_DEPENDENT | 1 | 1 |
| 09_bitemporal | s09_bitemporal_tgt | GREEN | YES | COMPLETE | HANDLED | 5 | 5 |
