# M3 Baseline Evaluation Report

## popularity
Queries evaluated: 44

### Overall Metrics
| K | Recall@K | MRR@K | nDCG@K |
|---|---------|-------|--------|
| 1 | 0.0018 | 0.0455 | 0.0455 |
| 3 | 0.0080 | 0.0682 | 0.0401 |
| 5 | 0.0080 | 0.0682 | 0.0290 |
| 10 | 0.0080 | 0.0682 | 0.0192 |
| 20 | 0.0170 | 0.0712 | 0.0189 |
| 50 | 0.0296 | 0.0726 | 0.0210 |

### Stratified by label_cardinality_bin
| label_cardinality_bin | N | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---------|-------|--------|
| 1 | 9 | 0.0000 | 0.0000 | 0.0000 |
| 2-3 | 12 | 0.0000 | 0.0000 | 0.0000 |
| 4-7 | 9 | 0.0000 | 0.0000 | 0.0000 |
| 8+ | 14 | 0.0251 | 0.2143 | 0.0603 |

### Stratified by doc_type_id
| doc_type_id | N | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---------|-------|--------|
| UNKNOWN | 44 | 0.0080 | 0.0682 | 0.0192 |

---

## bm25
Queries evaluated: 44

### Overall Metrics
| K | Recall@K | MRR@K | nDCG@K |
|---|---------|-------|--------|
| 1 | 0.0286 | 0.1364 | 0.1364 |
| 3 | 0.0387 | 0.1477 | 0.0895 |
| 5 | 0.0731 | 0.1591 | 0.0916 |
| 10 | 0.0746 | 0.1591 | 0.0794 |
| 20 | 0.0867 | 0.1642 | 0.0764 |
| 50 | 0.1026 | 0.1659 | 0.0813 |

### Popularity Dominance Check
- Beats popularity: Yes
- Model Recall@10: 0.0746
- Popularity Recall@10: 0.008
- Relative improvement: 834.6%

### Stratified by label_cardinality_bin
| label_cardinality_bin | N | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---------|-------|--------|
| 1 | 9 | 0.2222 | 0.1389 | 0.1590 |
| 2-3 | 12 | 0.0694 | 0.0625 | 0.0467 |
| 4-7 | 9 | 0.0000 | 0.0000 | 0.0000 |
| 8+ | 14 | 0.0320 | 0.3571 | 0.1072 |

### Stratified by doc_type_id
| doc_type_id | N | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---------|-------|--------|
| UNKNOWN | 44 | 0.0746 | 0.1591 | 0.0794 |

