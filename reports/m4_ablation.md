# Ablation Report

## Ablation Study

| Model | Config | Recall@10 | MRR@10 | nDCG@10 |
|-------|--------|-----------|--------|---------|
| bm25 | {'max_features': 5000, 'n_retrieve': 50} | 0.1409 | 0.2015 | 0.1331 |
| bm25 | {'max_features': 10000, 'n_retrieve': 50} | 0.1477 | 0.2077 | 0.1381 |
| bm25 | {'max_features': 20000, 'n_retrieve': 50} | 0.1537 | 0.2148 | 0.1469 |
| bm25 | {'max_features': 5000, 'n_retrieve': 100} | 0.1115 | 0.1808 | 0.1143 |
| bm25 | {'max_features': 10000, 'n_retrieve': 100} | 0.1262 | 0.1795 | 0.1194 |
| bm25 | {'max_features': 20000, 'n_retrieve': 100} | 0.1387 | 0.1933 | 0.1309 |
| bm25 | {'max_features': 5000, 'n_retrieve': 200} | 0.1027 | 0.1398 | 0.0899 |
| bm25 | {'max_features': 10000, 'n_retrieve': 200} | 0.1083 | 0.1405 | 0.0950 |
| bm25 | {'max_features': 20000, 'n_retrieve': 200} | 0.1116 | 0.1558 | 0.1037 |
| hybrid | {'alpha': 0.3, 'n_retrieve': 100} | 0.0623 | 0.1273 | 0.0632 |
| hybrid | {'alpha': 0.5, 'n_retrieve': 100} | 0.0856 | 0.1423 | 0.0829 |
| hybrid | {'alpha': 0.7, 'n_retrieve': 100} | 0.1070 | 0.1519 | 0.0997 |

