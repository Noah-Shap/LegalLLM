# M3 Baseline Evaluation Report

## popularity
Queries evaluated: 152

### Overall Metrics
| K | Recall@K | MRR@K | nDCG@K |
|---|---------|-------|--------|
| 1 | 0.0035 | 0.0132 | 0.0132 |
| 3 | 0.0090 | 0.0296 | 0.0191 |
| 5 | 0.0111 | 0.0375 | 0.0201 |
| 10 | 0.0194 | 0.0453 | 0.0212 |
| 20 | 0.0495 | 0.0512 | 0.0298 |
| 50 | 0.0629 | 0.0532 | 0.0346 |

### Stratified by label_cardinality_bin
| label_cardinality_bin | N | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---------|-------|--------|
| 1 | 29 | 0.0000 | 0.0000 | 0.0000 |
| 2-3 | 35 | 0.0333 | 0.0417 | 0.0285 |
| 4-7 | 32 | 0.0130 | 0.0074 | 0.0067 |
| 8+ | 56 | 0.0244 | 0.0926 | 0.0360 |

### Stratified by doc_type_id
| doc_type_id | N | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---------|-------|--------|
| MERITS_SCOTUS | 2 | 0.0200 | 0.0714 | 0.0367 |
| UNKNOWN | 150 | 0.0194 | 0.0449 | 0.0210 |

---

## bm25
Queries evaluated: 152

### Overall Metrics
| K | Recall@K | MRR@K | nDCG@K |
|---|---------|-------|--------|
| 1 | 0.0216 | 0.0987 | 0.0987 |
| 3 | 0.0614 | 0.1546 | 0.1148 |
| 5 | 0.0914 | 0.1678 | 0.1172 |
| 10 | 0.1262 | 0.1795 | 0.1194 |
| 20 | 0.1688 | 0.1847 | 0.1268 |
| 50 | 0.1991 | 0.1864 | 0.1358 |

### Popularity Dominance Check
- Beats popularity: Yes
- Model Recall@10: 0.1262
- Popularity Recall@10: 0.0194
- Relative improvement: 550.1%

### Stratified by label_cardinality_bin
| label_cardinality_bin | N | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---------|-------|--------|
| 1 | 29 | 0.1034 | 0.0463 | 0.0593 |
| 2-3 | 35 | 0.1952 | 0.1487 | 0.1335 |
| 4-7 | 32 | 0.1673 | 0.1850 | 0.1541 |
| 8+ | 56 | 0.0714 | 0.2646 | 0.1219 |

### Stratified by doc_type_id
| doc_type_id | N | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---------|-------|--------|
| MERITS_SCOTUS | 2 | 0.0400 | 0.2500 | 0.1168 |
| UNKNOWN | 150 | 0.1274 | 0.1786 | 0.1194 |

