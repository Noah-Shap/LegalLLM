# Evaluation Report

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

## Error Analysis: popularity

- Total queries: 152
- Zero-hit queries: 130 (85.5%)
- Total hits in top-K: 24

### Hit Position Distribution
| Position | Count |
|----------|-------|
| 1 | 2 |
| 2-3 | 7 |
| 4-5 | 5 |
| 6-10 | 10 |

### Zero-Hit Rate by Cardinality
| Cardinality | Queries | Zero-Hit | Rate |
|-------------|---------|----------|------|
| 1 | 29 | 29 | 100.0% |
| 2-3 | 35 | 32 | 91.4% |
| 4-7 | 32 | 30 | 93.8% |
| 8+ | 56 | 39 | 69.6% |

### Hardest Targets (top 10)
| Case ID | Miss Rate | Appearances |
|---------|-----------|-------------|
| 112881 | 100.0% | 5 |
| 118385 | 100.0% | 4 |
| 821306 | 100.0% | 4 |
| 103355 | 100.0% | 4 |
| 112404 | 100.0% | 4 |
| 109881 | 100.0% | 4 |
| 4511150 | 100.0% | 3 |
| 110661 | 100.0% | 3 |
| 107701 | 100.0% | 3 |
| 108348 | 100.0% | 3 |

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

## Error Analysis: bm25

- Total queries: 152
- Zero-hit queries: 96 (63.2%)
- Total hits in top-K: 105

### Hit Position Distribution
| Position | Count |
|----------|-------|
| 1 | 15 |
| 2-3 | 35 |
| 4-5 | 23 |
| 6-10 | 32 |

### Zero-Hit Rate by Cardinality
| Cardinality | Queries | Zero-Hit | Rate |
|-------------|---------|----------|------|
| 1 | 29 | 26 | 89.7% |
| 2-3 | 35 | 21 | 60.0% |
| 4-7 | 32 | 21 | 65.6% |
| 8+ | 56 | 28 | 50.0% |

### Hardest Targets (top 10)
| Case ID | Miss Rate | Appearances |
|---------|-----------|-------------|
| 118385 | 100.0% | 4 |
| 103355 | 100.0% | 4 |
| 4511150 | 100.0% | 3 |
| 110661 | 100.0% | 3 |
| 107701 | 100.0% | 3 |
| 108348 | 100.0% | 3 |
| 111688 | 100.0% | 3 |
| 112774 | 100.0% | 3 |
| 118098 | 100.0% | 3 |
| 102353 | 100.0% | 3 |

---

## hybrid
Queries evaluated: 152

### Overall Metrics
| K | Recall@K | MRR@K | nDCG@K |
|---|---------|-------|--------|
| 1 | 0.0131 | 0.0789 | 0.0789 |
| 3 | 0.0435 | 0.1239 | 0.0868 |
| 5 | 0.0587 | 0.1357 | 0.0816 |
| 10 | 0.0856 | 0.1423 | 0.0829 |
| 20 | 0.1154 | 0.1487 | 0.0907 |
| 50 | 0.1780 | 0.1519 | 0.1070 |

### Popularity Dominance Check
- Beats popularity: Yes
- Model Recall@10: 0.0856
- Popularity Recall@10: 0.0194
- Relative improvement: 340.7%

### Stratified by label_cardinality_bin
| label_cardinality_bin | N | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---------|-------|--------|
| 1 | 29 | 0.0690 | 0.0207 | 0.0317 |
| 2-3 | 35 | 0.1190 | 0.0950 | 0.0783 |
| 4-7 | 32 | 0.1324 | 0.1719 | 0.1285 |
| 8+ | 56 | 0.0465 | 0.2181 | 0.0861 |

### Stratified by doc_type_id
| doc_type_id | N | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---------|-------|--------|
| MERITS_SCOTUS | 2 | 0.0200 | 0.2500 | 0.0694 |
| UNKNOWN | 150 | 0.0865 | 0.1409 | 0.0830 |

---

## Error Analysis: hybrid

- Total queries: 152
- Zero-hit queries: 110 (72.4%)
- Total hits in top-K: 72

### Hit Position Distribution
| Position | Count |
|----------|-------|
| 1 | 12 |
| 2-3 | 26 |
| 4-5 | 12 |
| 6-10 | 22 |

### Zero-Hit Rate by Cardinality
| Cardinality | Queries | Zero-Hit | Rate |
|-------------|---------|----------|------|
| 1 | 29 | 27 | 93.1% |
| 2-3 | 35 | 26 | 74.3% |
| 4-7 | 32 | 24 | 75.0% |
| 8+ | 56 | 33 | 58.9% |

### Hardest Targets (top 10)
| Case ID | Miss Rate | Appearances |
|---------|-----------|-------------|
| 118385 | 100.0% | 4 |
| 103355 | 100.0% | 4 |
| 4511150 | 100.0% | 3 |
| 110661 | 100.0% | 3 |
| 107701 | 100.0% | 3 |
| 108348 | 100.0% | 3 |
| 111688 | 100.0% | 3 |
| 112774 | 100.0% | 3 |
| 4892570 | 100.0% | 3 |
| 118098 | 100.0% | 3 |

---

## reranker
Queries evaluated: 152

### Overall Metrics
| K | Recall@K | MRR@K | nDCG@K |
|---|---------|-------|--------|
| 1 | 0.0090 | 0.0592 | 0.0592 |
| 3 | 0.0337 | 0.1075 | 0.0733 |
| 5 | 0.0500 | 0.1229 | 0.0714 |
| 10 | 0.0716 | 0.1297 | 0.0721 |
| 20 | 0.1049 | 0.1361 | 0.0800 |
| 50 | 0.1604 | 0.1381 | 0.0963 |

### Popularity Dominance Check
- Beats popularity: Yes
- Model Recall@10: 0.0716
- Popularity Recall@10: 0.0194
- Relative improvement: 268.5%

### Stratified by label_cardinality_bin
| label_cardinality_bin | N | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---------|-------|--------|
| 1 | 29 | 0.0345 | 0.0086 | 0.0149 |
| 2-3 | 35 | 0.1095 | 0.1032 | 0.0802 |
| 4-7 | 32 | 0.1064 | 0.1253 | 0.0902 |
| 8+ | 56 | 0.0471 | 0.2116 | 0.0863 |

### Stratified by doc_type_id
| doc_type_id | N | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---------|-------|--------|
| MERITS_SCOTUS | 2 | 0.0400 | 0.2500 | 0.1061 |
| UNKNOWN | 150 | 0.0720 | 0.1281 | 0.0716 |

---

## Error Analysis: reranker

- Total queries: 152
- Zero-hit queries: 109 (71.7%)
- Total hits in top-K: 68

### Hit Position Distribution
| Position | Count |
|----------|-------|
| 1 | 9 |
| 2-3 | 24 |
| 4-5 | 12 |
| 6-10 | 23 |

### Zero-Hit Rate by Cardinality
| Cardinality | Queries | Zero-Hit | Rate |
|-------------|---------|----------|------|
| 1 | 29 | 28 | 96.6% |
| 2-3 | 35 | 26 | 74.3% |
| 4-7 | 32 | 23 | 71.9% |
| 8+ | 56 | 32 | 57.1% |

### Hardest Targets (top 10)
| Case ID | Miss Rate | Appearances |
|---------|-----------|-------------|
| 118385 | 100.0% | 4 |
| 821306 | 100.0% | 4 |
| 103355 | 100.0% | 4 |
| 4511150 | 100.0% | 3 |
| 110661 | 100.0% | 3 |
| 107701 | 100.0% | 3 |
| 108348 | 100.0% | 3 |
| 111688 | 100.0% | 3 |
| 112774 | 100.0% | 3 |
| 118098 | 100.0% | 3 |

---

## Model Comparison: popularity vs bm25

| Metric | Value |
|--------|-------|
| popularity wins | 1 (0.7%) |
| bm25 wins | 42 (27.6%) |
| Ties | 109 |
| Total queries | 152 |

---

## Model Comparison: bm25 vs hybrid

| Metric | Value |
|--------|-------|
| bm25 wins | 25 (16.4%) |
| hybrid wins | 2 (1.3%) |
| Ties | 125 |
| Total queries | 152 |

---

## Model Comparison: hybrid vs reranker

| Metric | Value |
|--------|-------|
| hybrid wins | 9 (5.9%) |
| reranker wins | 11 (7.2%) |
| Ties | 132 |
| Total queries | 152 |

