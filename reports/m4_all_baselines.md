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

---

## dense
Queries evaluated: 152

### Overall Metrics
| K | Recall@K | MRR@K | nDCG@K |
|---|---------|-------|--------|
| 1 | 0.0071 | 0.0461 | 0.0461 |
| 3 | 0.0231 | 0.0800 | 0.0529 |
| 5 | 0.0254 | 0.0843 | 0.0444 |
| 10 | 0.0370 | 0.0899 | 0.0431 |
| 20 | 0.0582 | 0.0933 | 0.0497 |
| 50 | 0.1064 | 0.0957 | 0.0614 |

### Popularity Dominance Check
- Beats popularity: Yes
- Model Recall@10: 0.037
- Popularity Recall@10: 0.0194
- Relative improvement: 90.7%

### Stratified by label_cardinality_bin
| label_cardinality_bin | N | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---------|-------|--------|
| 1 | 29 | 0.0000 | 0.0000 | 0.0000 |
| 2-3 | 35 | 0.0333 | 0.0219 | 0.0197 |
| 4-7 | 32 | 0.0941 | 0.1164 | 0.0919 |
| 8+ | 56 | 0.0259 | 0.1637 | 0.0523 |

### Stratified by doc_type_id
| doc_type_id | N | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---------|-------|--------|
| MERITS_SCOTUS | 2 | 0.0200 | 0.5000 | 0.1100 |
| UNKNOWN | 150 | 0.0373 | 0.0844 | 0.0422 |

