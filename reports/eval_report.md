# RAG Evaluation Report

Generated at: 2026-05-23T09:46:33
Dataset size: 16
Elapsed: 85094.80 ms

## Ablation Summary

| Config | Retrieval | Rerank | Metadata Adj. | Recall@5 | MRR@10 | Citation Acc. | Tool Success |
|---|---|---:|---:|---:|---:|---:|---:|
| bm25_only | bm25 | False | False | 75.00% | 68.33% | 62.50% | 100.00% |
| vector_only | vector | False | False | 68.75% | 60.17% | 50.00% | 100.00% |
| hybrid_no_rerank | hybrid | False | False | 81.25% | 63.65% | 50.00% | 100.00% |
| hybrid_rerank | hybrid | True | False | 100.00% | 85.62% | 75.00% | 100.00% |
| hybrid_rerank_metadata | hybrid | True | True | 100.00% | 84.58% | 75.00% | 100.00% |

## Improvement vs Baseline: bm25_only

| Config | Recall@5 Delta | MRR@10 Delta | Citation Acc. Delta | Tool Success Delta |
|---|---:|---:|---:|---:|
| vector_only | -6.25 pp / -8.33% | -8.16 pp / -11.94% | -12.50 pp / -20.00% | +0.00 pp / +0.00% |
| hybrid_no_rerank | +6.25 pp / +8.33% | -4.69 pp / -6.86% | -12.50 pp / -20.00% | +0.00 pp / +0.00% |
| hybrid_rerank | +25.00 pp / +33.33% | +17.29 pp / +25.30% | +12.50 pp / +20.00% | +0.00 pp / +0.00% |
| hybrid_rerank_metadata | +25.00 pp / +33.33% | +16.25 pp / +23.78% | +12.50 pp / +20.00% | +0.00 pp / +0.00% |

## Case Details: bm25_only

| Hit@5 | RR | Question | Gold Chunks | Retrieved Top 5 |
|---:|---:|---|---|---|
| True | 1.000 | What does HTTP status code 404 mean? | rfc9110-http-semantics_c0812 | rfc9110-http-semantics_c0812, rfc9110-http-semantics_c0997, rfc9110-http-semantics_c0749, rfc9110-http-semantics_c0838, rfc9110-http-semantics_c0849 |
| True | 1.000 | Which HTTP responses are heuristically cacheable? | rfc9110-http-semantics_c0749 | rfc9110-http-semantics_c0749, rfc9110-http-semantics_c0756, rfc9110-http-semantics_c0571, rfc9110-http-semantics_c0566, rfc9110-http-semantics_c0333 |
| True | 0.500 | How does TLS 1.3 discuss replay protection for 0-RTT data? | rfc8446-tls13_c0406, rfc8446-tls13_c0273 | rfc8446-tls13_c0045, rfc8446-tls13_c0406, rfc8446-tls13_c0273, rfc8446-tls13_c0282, rfc8446-tls13_c0373 |
| True | 0.333 | What is the QUIC transport protocol? | rfc9000-quic_c0000 | rfc9000-quic_c0292, rfc9000-quic_c0196, rfc9000-quic_c0000, rfc9000-quic_c0560, rfc9000-quic_c0312 |
| True | 1.000 | How can TLS 1.3 PSKs provide forward secrecy? | rfc8446-tls13_c0038 | rfc8446-tls13_c0038, rfc8446-tls13_c0399, rfc8446-tls13_c0385, rfc8446-tls13_c0321, rfc8446-tls13_c0383 |
| True | 1.000 | What is the TLS 1.3 KeyUpdate handshake message used for? | rfc8446-tls13_c0212, rfc8446-tls13_c0210 | rfc8446-tls13_c0210, rfc8446-tls13_c0076, rfc8446-tls13_c0078, rfc8446-tls13_c0411, rfc8446-tls13_c0197 |
| True | 1.000 | Which cipher suite must a TLS-compliant application implement? | rfc8446-tls13_c0290 | rfc8446-tls13_c0290, rfc8446-tls13_c0087, rfc8446-tls13_c0295, rfc8446-tls13_c0291, rfc8446-tls13_c0080 |
| False | 0.000 | How does QUIC use connection IDs for migration? | rfc9000-quic_c0356 | rfc9000-quic_c0264, rfc9000-quic_c0268, rfc9000-quic_c0379, rfc9000-quic_c0528, rfc9000-quic_c0282 |
| True | 1.000 | What abstraction do QUIC streams provide to applications? | rfc9000-quic_c0209 | rfc9000-quic_c0209, rfc9000-quic_c0216, rfc9000-quic_c0200, rfc9000-quic_c0215, rfc9000-quic_c0000 |
| True | 1.000 | How does QUIC perform path validation? | rfc9000-quic_c0348, rfc9000-quic_c0354, rfc9000-quic_c0344, rfc9000-quic_c0349 | rfc9000-quic_c0349, rfc9000-quic_c0354, rfc9000-quic_c0484, rfc9000-quic_c0385, rfc9000-quic_c0355 |
| True | 1.000 | When does a QUIC connection idle timeout occur? | rfc9000-quic_c0392, rfc9000-quic_c0393, rfc9000-quic_c0389 | rfc9000-quic_c0392, rfc9000-quic_c0388, rfc9000-quic_c0393, rfc9000-quic_c0390, rfc9000-quic_c0389 |
| False | 0.000 | What does the HTTP GET method request? | rfc9110-http-semantics_c0543 | rfc9110-http-semantics_c0541, rfc9110-http-semantics_c0410, rfc9110-http-semantics_c0798, rfc9110-http-semantics_c0557, rfc9110-http-semantics_c0779 |
| False | 0.100 | What does the HTTP PUT method request? | rfc9110-http-semantics_c0554 | rfc9110-http-semantics_c0557, rfc9110-http-semantics_c0538, rfc9110-http-semantics_c0534, rfc9110-http-semantics_c0672, rfc9110-http-semantics_c0925 |
| False | 0.000 | What does the HTTP Content-Type header field indicate? | rfc9110-http-semantics_c0473 | rfc9110-http-semantics_c0480, rfc9110-http-semantics_c0767, rfc9110-http-semantics_c0831, rfc9110-http-semantics_c0824, rfc9110-http-semantics_c0524 |
| True | 1.000 | How are weak and strong validators different in HTTP? | rfc9110-http-semantics_c0504 | rfc9110-http-semantics_c0504, rfc9110-http-semantics_c0509, rfc9110-http-semantics_c0522, rfc9110-http-semantics_c0518, rfc9110-http-semantics_c0093 |
| True | 1.000 | What is the purpose of QUIC immediate close? | rfc9000-quic_c0395, rfc9000-quic_c0394 | rfc9000-quic_c0394, rfc9000-quic_c0388, rfc9000-quic_c0078, rfc9000-quic_c0075, rfc9000-quic_c0391 |

### Missed Cases

- How does QUIC use connection IDs for migration?
- What does the HTTP GET method request?
- What does the HTTP PUT method request?
- What does the HTTP Content-Type header field indicate?

## Case Details: vector_only

| Hit@5 | RR | Question | Gold Chunks | Retrieved Top 5 |
|---:|---:|---|---|---|
| True | 1.000 | What does HTTP status code 404 mean? | rfc9110-http-semantics_c0812 | rfc9110-http-semantics_c0812, rfc9110-http-semantics_c0746, rfc9110-http-semantics_c0749, rfc9110-http-semantics_c0747, rfc9110-http-semantics_c0828 |
| False | 0.000 | Which HTTP responses are heuristically cacheable? | rfc9110-http-semantics_c0749 | rfc9110-http-semantics_c0333, rfc9110-http-semantics_c0332, rfc9110-http-semantics_c0541, rfc9110-http-semantics_c0792, rfc9110-http-semantics_c0553 |
| True | 1.000 | How does TLS 1.3 discuss replay protection for 0-RTT data? | rfc8446-tls13_c0406, rfc8446-tls13_c0273 | rfc8446-tls13_c0273, rfc8446-tls13_c0045, rfc8446-tls13_c0044, rfc8446-tls13_c0409, rfc9000-quic_c0536 |
| False | 0.167 | What is the QUIC transport protocol? | rfc9000-quic_c0000 | rfc9000-quic_c0196, rfc9000-quic_c0633, rfc9000-quic_c0203, rfc9000-quic_c0200, rfc9000-quic_c0309 |
| True | 1.000 | How can TLS 1.3 PSKs provide forward secrecy? | rfc8446-tls13_c0038 | rfc8446-tls13_c0038, rfc8446-tls13_c0412, rfc8446-tls13_c0411, rfc8446-tls13_c0040, rfc8446-tls13_c0316 |
| False | 0.111 | What is the TLS 1.3 KeyUpdate handshake message used for? | rfc8446-tls13_c0212, rfc8446-tls13_c0210 | rfc8446-tls13_c0063, rfc8446-tls13_c0199, rfc8446-tls13_c0028, rfc8446-tls13_c0254, rfc8446-tls13_c0161 |
| True | 1.000 | Which cipher suite must a TLS-compliant application implement? | rfc8446-tls13_c0290 | rfc8446-tls13_c0290, rfc8446-tls13_c0377, rfc8446-tls13_c0357, rfc8446-tls13_c0299, rfc8446-tls13_c0355 |
| True | 1.000 | How does QUIC use connection IDs for migration? | rfc9000-quic_c0356 | rfc9000-quic_c0356, rfc9000-quic_c0261, rfc9000-quic_c0520, rfc9000-quic_c0274, rfc9000-quic_c0521 |
| True | 1.000 | What abstraction do QUIC streams provide to applications? | rfc9000-quic_c0209 | rfc9000-quic_c0209, rfc9000-quic_c0217, rfc9000-quic_c0200, rfc9000-quic_c0216, rfc9000-quic_c0197 |
| True | 0.333 | How does QUIC perform path validation? | rfc9000-quic_c0348, rfc9000-quic_c0354, rfc9000-quic_c0344, rfc9000-quic_c0349 | rfc9000-quic_c0647, rfc9000-quic_c0662, rfc9000-quic_c0354, rfc9000-quic_c0633, rfc9000-quic_c0504 |
| True | 0.500 | When does a QUIC connection idle timeout occur? | rfc9000-quic_c0392, rfc9000-quic_c0393, rfc9000-quic_c0389 | rfc9000-quic_c0388, rfc9000-quic_c0392, rfc9000-quic_c0393, rfc9000-quic_c0395, rfc9000-quic_c0198 |
| False | 0.167 | What does the HTTP GET method request? | rfc9110-http-semantics_c0543 | rfc9110-http-semantics_c0415, rfc9110-http-semantics_c0527, rfc9110-http-semantics_c0416, rfc9110-http-semantics_c0545, rfc9110-http-semantics_c0798 |
| True | 0.250 | What does the HTTP PUT method request? | rfc9110-http-semantics_c0554 | rfc9110-http-semantics_c0560, rfc9110-http-semantics_c0557, rfc9110-http-semantics_c0562, rfc9110-http-semantics_c0554, rfc9110-http-semantics_c0527 |
| True | 1.000 | What does the HTTP Content-Type header field indicate? | rfc9110-http-semantics_c0473 | rfc9110-http-semantics_c0473, rfc9110-http-semantics_c0497, rfc9110-http-semantics_c0321, rfc9110-http-semantics_c0365, rfc9110-http-semantics_c0407 |
| True | 1.000 | How are weak and strong validators different in HTTP? | rfc9110-http-semantics_c0504 | rfc9110-http-semantics_c0504, rfc9110-http-semantics_c0509, rfc9110-http-semantics_c0702, rfc9110-http-semantics_c0507, rfc9110-http-semantics_c0522 |
| False | 0.100 | What is the purpose of QUIC immediate close? | rfc9000-quic_c0395, rfc9000-quic_c0394 | rfc9000-quic_c0397, rfc9000-quic_c0668, rfc9000-quic_c0406, rfc9000-quic_c0388, rfc9000-quic_c0633 |

### Missed Cases

- Which HTTP responses are heuristically cacheable?
- What is the QUIC transport protocol?
- What is the TLS 1.3 KeyUpdate handshake message used for?
- What does the HTTP GET method request?
- What is the purpose of QUIC immediate close?

## Case Details: hybrid_no_rerank

| Hit@5 | RR | Question | Gold Chunks | Retrieved Top 5 |
|---:|---:|---|---|---|
| True | 1.000 | What does HTTP status code 404 mean? | rfc9110-http-semantics_c0812 | rfc9110-http-semantics_c0812, rfc9110-http-semantics_c0749, rfc9110-http-semantics_c0746, rfc9110-http-semantics_c0747, rfc9110-http-semantics_c0828 |
| False | 0.000 | Which HTTP responses are heuristically cacheable? | rfc9110-http-semantics_c0749 | rfc9110-http-semantics_c0333, rfc9110-http-semantics_c0792, rfc9110-http-semantics_c0332, rfc9110-http-semantics_c0541, rfc9110-http-semantics_c0553 |
| True | 0.500 | How does TLS 1.3 discuss replay protection for 0-RTT data? | rfc8446-tls13_c0406, rfc8446-tls13_c0273 | rfc8446-tls13_c0045, rfc8446-tls13_c0273, rfc8446-tls13_c0409, rfc8446-tls13_c0406, rfc8446-tls13_c0044 |
| True | 0.333 | What is the QUIC transport protocol? | rfc9000-quic_c0000 | rfc9000-quic_c0196, rfc9000-quic_c0203, rfc9000-quic_c0000, rfc9000-quic_c0292, rfc9000-quic_c0201 |
| True | 1.000 | How can TLS 1.3 PSKs provide forward secrecy? | rfc8446-tls13_c0038 | rfc8446-tls13_c0038, rfc8446-tls13_c0412, rfc8446-tls13_c0040, rfc8446-tls13_c0383, rfc8446-tls13_c0411 |
| True | 1.000 | What is the TLS 1.3 KeyUpdate handshake message used for? | rfc8446-tls13_c0212, rfc8446-tls13_c0210 | rfc8446-tls13_c0210, rfc8446-tls13_c0063, rfc8446-tls13_c0199, rfc8446-tls13_c0028, rfc8446-tls13_c0254 |
| True | 1.000 | Which cipher suite must a TLS-compliant application implement? | rfc8446-tls13_c0290 | rfc8446-tls13_c0290, rfc8446-tls13_c0357, rfc8446-tls13_c0291, rfc8446-tls13_c0295, rfc8446-tls13_c0354 |
| True | 0.333 | How does QUIC use connection IDs for migration? | rfc9000-quic_c0356 | rfc9000-quic_c0520, rfc9000-quic_c0269, rfc9000-quic_c0356, rfc9000-quic_c0261, rfc9000-quic_c0274 |
| True | 1.000 | What abstraction do QUIC streams provide to applications? | rfc9000-quic_c0209 | rfc9000-quic_c0209, rfc9000-quic_c0200, rfc9000-quic_c0216, rfc9000-quic_c0217, rfc9000-quic_c0197 |
| True | 1.000 | How does QUIC perform path validation? | rfc9000-quic_c0348, rfc9000-quic_c0354, rfc9000-quic_c0344, rfc9000-quic_c0349 | rfc9000-quic_c0354, rfc9000-quic_c0647, rfc9000-quic_c0662, rfc9000-quic_c0633, rfc9000-quic_c0504 |
| True | 0.500 | When does a QUIC connection idle timeout occur? | rfc9000-quic_c0392, rfc9000-quic_c0393, rfc9000-quic_c0389 | rfc9000-quic_c0388, rfc9000-quic_c0392, rfc9000-quic_c0393, rfc9000-quic_c0389, rfc9000-quic_c0074 |
| False | 0.167 | What does the HTTP GET method request? | rfc9110-http-semantics_c0543 | rfc9110-http-semantics_c0798, rfc9110-http-semantics_c0527, rfc9110-http-semantics_c0415, rfc9110-http-semantics_c0416, rfc9110-http-semantics_c0545 |
| True | 0.250 | What does the HTTP PUT method request? | rfc9110-http-semantics_c0554 | rfc9110-http-semantics_c0557, rfc9110-http-semantics_c0562, rfc9110-http-semantics_c0527, rfc9110-http-semantics_c0554, rfc9110-http-semantics_c0798 |
| True | 1.000 | What does the HTTP Content-Type header field indicate? | rfc9110-http-semantics_c0473 | rfc9110-http-semantics_c0473, rfc9110-http-semantics_c0497, rfc9110-http-semantics_c0321, rfc9110-http-semantics_c0365, rfc9110-http-semantics_c0407 |
| True | 1.000 | How are weak and strong validators different in HTTP? | rfc9110-http-semantics_c0504 | rfc9110-http-semantics_c0504, rfc9110-http-semantics_c0509, rfc9110-http-semantics_c0522, rfc9110-http-semantics_c0093, rfc9110-http-semantics_c0506 |
| False | 0.100 | What is the purpose of QUIC immediate close? | rfc9000-quic_c0395, rfc9000-quic_c0394 | rfc9000-quic_c0388, rfc9000-quic_c0397, rfc9000-quic_c0406, rfc9000-quic_c0668, rfc9000-quic_c0633 |

### Missed Cases

- Which HTTP responses are heuristically cacheable?
- What does the HTTP GET method request?
- What is the purpose of QUIC immediate close?

## Case Details: hybrid_rerank

| Hit@5 | RR | Question | Gold Chunks | Retrieved Top 5 |
|---:|---:|---|---|---|
| True | 1.000 | What does HTTP status code 404 mean? | rfc9110-http-semantics_c0812 | rfc9110-http-semantics_c0812, rfc9110-http-semantics_c0818, rfc9110-http-semantics_c0811, rfc9110-http-semantics_c0749, rfc9110-http-semantics_c0838 |
| True | 0.200 | Which HTTP responses are heuristically cacheable? | rfc9110-http-semantics_c0749 | rfc9110-http-semantics_c0806, rfc9110-http-semantics_c0819, rfc9110-http-semantics_c0766, rfc9110-http-semantics_c0795, rfc9110-http-semantics_c0749 |
| True | 0.500 | How does TLS 1.3 discuss replay protection for 0-RTT data? | rfc8446-tls13_c0406, rfc8446-tls13_c0273 | rfc8446-tls13_c0045, rfc8446-tls13_c0273, rfc8446-tls13_c0406, rfc8446-tls13_c0409, rfc8446-tls13_c0407 |
| True | 0.500 | What is the QUIC transport protocol? | rfc9000-quic_c0000 | rfc9000-quic_c0196, rfc9000-quic_c0000, rfc9000-quic_c0292, rfc9000-quic_c0633, rfc9000-quic_c0203 |
| True | 1.000 | How can TLS 1.3 PSKs provide forward secrecy? | rfc8446-tls13_c0038 | rfc8446-tls13_c0038, rfc8446-tls13_c0383, rfc8446-tls13_c0384, rfc8446-tls13_c0397, rfc8446-tls13_c0040 |
| True | 1.000 | What is the TLS 1.3 KeyUpdate handshake message used for? | rfc8446-tls13_c0212, rfc8446-tls13_c0210 | rfc8446-tls13_c0210, rfc8446-tls13_c0042, rfc8446-tls13_c0166, rfc8446-tls13_c0038, rfc8446-tls13_c0076 |
| True | 1.000 | Which cipher suite must a TLS-compliant application implement? | rfc8446-tls13_c0290 | rfc8446-tls13_c0290, rfc8446-tls13_c0377, rfc8446-tls13_c0291, rfc8446-tls13_c0357, rfc8446-tls13_c0295 |
| True | 1.000 | How does QUIC use connection IDs for migration? | rfc9000-quic_c0356 | rfc9000-quic_c0356, rfc9000-quic_c0198, rfc9000-quic_c0380, rfc9000-quic_c0260, rfc9000-quic_c0261 |
| True | 1.000 | What abstraction do QUIC streams provide to applications? | rfc9000-quic_c0209 | rfc9000-quic_c0209, rfc9000-quic_c0216, rfc9000-quic_c0200, rfc9000-quic_c0000, rfc9000-quic_c0217 |
| True | 1.000 | How does QUIC perform path validation? | rfc9000-quic_c0348, rfc9000-quic_c0354, rfc9000-quic_c0344, rfc9000-quic_c0349 | rfc9000-quic_c0349, rfc9000-quic_c0504, rfc9000-quic_c0484, rfc9000-quic_c0354, rfc9000-quic_c0198 |
| True | 1.000 | When does a QUIC connection idle timeout occur? | rfc9000-quic_c0392, rfc9000-quic_c0393, rfc9000-quic_c0389 | rfc9000-quic_c0393, rfc9000-quic_c0388, rfc9000-quic_c0392, rfc9000-quic_c0391, rfc9000-quic_c0395 |
| True | 1.000 | What does the HTTP GET method request? | rfc9110-http-semantics_c0543 | rfc9110-http-semantics_c0543, rfc9110-http-semantics_c0672, rfc9110-http-semantics_c0527, rfc9110-http-semantics_c0313, rfc9110-http-semantics_c0290 |
| True | 1.000 | What does the HTTP PUT method request? | rfc9110-http-semantics_c0554 | rfc9110-http-semantics_c0554, rfc9110-http-semantics_c0527, rfc9110-http-semantics_c0672, rfc9110-http-semantics_c0313, rfc9110-http-semantics_c0320 |
| True | 1.000 | What does the HTTP Content-Type header field indicate? | rfc9110-http-semantics_c0473 | rfc9110-http-semantics_c0473, rfc9110-http-semantics_c0480, rfc9110-http-semantics_c0483, rfc9110-http-semantics_c0497, rfc9110-http-semantics_c0660 |
| True | 1.000 | How are weak and strong validators different in HTTP? | rfc9110-http-semantics_c0504 | rfc9110-http-semantics_c0504, rfc9110-http-semantics_c0509, rfc9110-http-semantics_c0507, rfc9110-http-semantics_c0702, rfc9110-http-semantics_c0519 |
| True | 0.500 | What is the purpose of QUIC immediate close? | rfc9000-quic_c0395, rfc9000-quic_c0394 | rfc9000-quic_c0403, rfc9000-quic_c0394, rfc9000-quic_c0395, rfc9000-quic_c0406, rfc9000-quic_c0388 |

## Case Details: hybrid_rerank_metadata

| Hit@5 | RR | Question | Gold Chunks | Retrieved Top 5 |
|---:|---:|---|---|---|
| True | 1.000 | What does HTTP status code 404 mean? | rfc9110-http-semantics_c0812 | rfc9110-http-semantics_c0812, rfc9110-http-semantics_c0818, rfc9110-http-semantics_c0811, rfc9110-http-semantics_c0749, rfc9110-http-semantics_c0838 |
| True | 0.200 | Which HTTP responses are heuristically cacheable? | rfc9110-http-semantics_c0749 | rfc9110-http-semantics_c0806, rfc9110-http-semantics_c0819, rfc9110-http-semantics_c0766, rfc9110-http-semantics_c0795, rfc9110-http-semantics_c0749 |
| True | 0.500 | How does TLS 1.3 discuss replay protection for 0-RTT data? | rfc8446-tls13_c0406, rfc8446-tls13_c0273 | rfc8446-tls13_c0045, rfc8446-tls13_c0273, rfc8446-tls13_c0042, rfc9000-quic_c0536, rfc9000-quic_c0259 |
| True | 0.500 | What is the QUIC transport protocol? | rfc9000-quic_c0000 | rfc9000-quic_c0196, rfc9000-quic_c0000, rfc9000-quic_c0292, rfc9000-quic_c0633, rfc9000-quic_c0203 |
| True | 1.000 | How can TLS 1.3 PSKs provide forward secrecy? | rfc8446-tls13_c0038 | rfc8446-tls13_c0038, rfc8446-tls13_c0045, rfc8446-tls13_c0040, rfc8446-tls13_c0383, rfc8446-tls13_c0277 |
| True | 1.000 | What is the TLS 1.3 KeyUpdate handshake message used for? | rfc8446-tls13_c0212, rfc8446-tls13_c0210 | rfc8446-tls13_c0210, rfc8446-tls13_c0042, rfc8446-tls13_c0166, rfc8446-tls13_c0038, rfc8446-tls13_c0076 |
| True | 1.000 | Which cipher suite must a TLS-compliant application implement? | rfc8446-tls13_c0290 | rfc8446-tls13_c0290, rfc8446-tls13_c0291, rfc8446-tls13_c0295, rfc8446-tls13_c0152, rfc8446-tls13_c0117 |
| True | 1.000 | How does QUIC use connection IDs for migration? | rfc9000-quic_c0356 | rfc9000-quic_c0356, rfc9000-quic_c0198, rfc9000-quic_c0380, rfc9000-quic_c0260, rfc9000-quic_c0269 |
| True | 1.000 | What abstraction do QUIC streams provide to applications? | rfc9000-quic_c0209 | rfc9000-quic_c0209, rfc9000-quic_c0217, rfc9000-quic_c0216, rfc9000-quic_c0200, rfc9000-quic_c0000 |
| True | 1.000 | How does QUIC perform path validation? | rfc9000-quic_c0348, rfc9000-quic_c0354, rfc9000-quic_c0344, rfc9000-quic_c0349 | rfc9000-quic_c0349, rfc9000-quic_c0354, rfc9000-quic_c0504, rfc9000-quic_c0484, rfc9000-quic_c0198 |
| True | 1.000 | When does a QUIC connection idle timeout occur? | rfc9000-quic_c0392, rfc9000-quic_c0393, rfc9000-quic_c0389 | rfc9000-quic_c0393, rfc9000-quic_c0392, rfc9000-quic_c0388, rfc9000-quic_c0391, rfc9000-quic_c0395 |
| True | 1.000 | What does the HTTP GET method request? | rfc9110-http-semantics_c0543 | rfc9110-http-semantics_c0543, rfc9110-http-semantics_c0672, rfc9110-http-semantics_c0527, rfc9110-http-semantics_c0313, rfc9110-http-semantics_c0290 |
| True | 1.000 | What does the HTTP PUT method request? | rfc9110-http-semantics_c0554 | rfc9110-http-semantics_c0554, rfc9110-http-semantics_c0527, rfc9110-http-semantics_c0672, rfc9110-http-semantics_c0313, rfc9110-http-semantics_c0557 |
| True | 1.000 | What does the HTTP Content-Type header field indicate? | rfc9110-http-semantics_c0473 | rfc9110-http-semantics_c0473, rfc9110-http-semantics_c0480, rfc9110-http-semantics_c0660, rfc9110-http-semantics_c0483, rfc9110-http-semantics_c0497 |
| True | 1.000 | How are weak and strong validators different in HTTP? | rfc9110-http-semantics_c0504 | rfc9110-http-semantics_c0504, rfc9110-http-semantics_c0509, rfc9110-http-semantics_c0507, rfc9110-http-semantics_c0702, rfc9110-http-semantics_c0519 |
| True | 0.333 | What is the purpose of QUIC immediate close? | rfc9000-quic_c0395, rfc9000-quic_c0394 | rfc9000-quic_c0403, rfc9000-quic_c0406, rfc9000-quic_c0394, rfc9000-quic_c0395, rfc9000-quic_c0405 |

## Agent Evaluation: deterministic_workflow_agent

| Metric | Value |
|---|---:|
| AgentRunSuccessRate | 100.00% |
| AgentCitationHit@5 | 100.00% |
| AnswerKeywordCoverage | 81.25% |
| AgentNodeSuccessRate | 100.00% |
| AgentToolSuccessRate | 100.00% |
| AgentAvgLatencyMs | 1383.97 ms |

### Agent Case Details

| Citation Hit | Keyword Coverage | Node Success | Tool Success | Latency | Question | Citations | Matched Keywords |
|---:|---:|---:|---:|---:|---|---|---|
| True | 100.00% | 100.00% | 100.00% | 1798.78 ms | What does HTTP status code 404 mean? | rfc9110-http-semantics_c0812, rfc9110-http-semantics_c0818, rfc9110-http-semantics_c0811, rfc9110-http-semantics_c0749, rfc9110-http-semantics_c0838 | 404, Not Found, origin server |
| True | 100.00% | 100.00% | 100.00% | 967.35 ms | Which HTTP responses are heuristically cacheable? | rfc9110-http-semantics_c0806, rfc9110-http-semantics_c0819, rfc9110-http-semantics_c0766, rfc9110-http-semantics_c0749, rfc9110-http-semantics_c0792 | heuristically cacheable, 404, cache |
| True | 100.00% | 100.00% | 100.00% | 1919.85 ms | How does TLS 1.3 discuss replay protection for 0-RTT data? | rfc8446-tls13_c0045, rfc8446-tls13_c0273, rfc8446-tls13_c0042, rfc9000-quic_c0536, rfc9000-quic_c0259 | 0-RTT, replay, TLS |
| True | 100.00% | 100.00% | 100.00% | 1492.04 ms | What is the QUIC transport protocol? | rfc9000-quic_c0196, rfc9000-quic_c0000, rfc9000-quic_c0292, rfc9000-quic_c0633, rfc9000-quic_c0203 | QUIC, transport, UDP |
| True | 100.00% | 100.00% | 100.00% | 1587.87 ms | How can TLS 1.3 PSKs provide forward secrecy? | rfc8446-tls13_c0038, rfc8446-tls13_c0045, rfc8446-tls13_c0040, rfc8446-tls13_c0383, rfc8446-tls13_c0277 | PSK, DHE, forward secrecy |
| True | 66.67% | 100.00% | 100.00% | 1207.08 ms | What is the TLS 1.3 KeyUpdate handshake message used for? | rfc8446-tls13_c0210, rfc8446-tls13_c0042, rfc8446-tls13_c0166, rfc8446-tls13_c0038, rfc8446-tls13_c0076 | KeyUpdate, cryptographic keys |
| True | 100.00% | 100.00% | 100.00% | 1555.93 ms | Which cipher suite must a TLS-compliant application implement? | rfc8446-tls13_c0290, rfc8446-tls13_c0291, rfc8446-tls13_c0295, rfc8446-tls13_c0152, rfc8446-tls13_c0117 | TLS_AES_128_GCM_SHA256, MUST implement, cipher suite |
| True | 100.00% | 100.00% | 100.00% | 986.08 ms | How does QUIC use connection IDs for migration? | rfc9000-quic_c0356, rfc9000-quic_c0198, rfc9000-quic_c0380, rfc9000-quic_c0260, rfc9000-quic_c0269 | connection ID, endpoint addresses, migration |
| True | 66.67% | 100.00% | 100.00% | 1071.76 ms | What abstraction do QUIC streams provide to applications? | rfc9000-quic_c0209, rfc9000-quic_c0217, rfc9000-quic_c0216, rfc9000-quic_c0200, rfc9000-quic_c0000 | Streams, ordered byte-stream |
| True | 66.67% | 100.00% | 100.00% | 1300.02 ms | How does QUIC perform path validation? | rfc9000-quic_c0349, rfc9000-quic_c0354, rfc9000-quic_c0504, rfc9000-quic_c0484, rfc9000-quic_c0485 | PATH_CHALLENGE, path validation |
| True | 33.33% | 100.00% | 100.00% | 1030.04 ms | When does a QUIC connection idle timeout occur? | rfc9000-quic_c0393, rfc9000-quic_c0392, rfc9000-quic_c0388, rfc9000-quic_c0391, rfc9000-quic_c0395 | idle |
| True | 66.67% | 100.00% | 100.00% | 1636.15 ms | What does the HTTP GET method request? | rfc9110-http-semantics_c0543, rfc9110-http-semantics_c0672, rfc9110-http-semantics_c0527, rfc9110-http-semantics_c0313, rfc9110-http-semantics_c0320 | GET, target resource |
| True | 66.67% | 100.00% | 100.00% | 1779.96 ms | What does the HTTP PUT method request? | rfc9110-http-semantics_c0554, rfc9110-http-semantics_c0527, rfc9110-http-semantics_c0672, rfc9110-http-semantics_c0313, rfc9110-http-semantics_c0557 | PUT, representation |
| True | 100.00% | 100.00% | 100.00% | 1140.02 ms | What does the HTTP Content-Type header field indicate? | rfc9110-http-semantics_c0473, rfc9110-http-semantics_c0480, rfc9110-http-semantics_c0660, rfc9110-http-semantics_c0497, rfc9110-http-semantics_c0824 | Content-Type, media type, representation |
| True | 66.67% | 100.00% | 100.00% | 1613.96 ms | How are weak and strong validators different in HTTP? | rfc9110-http-semantics_c0504, rfc9110-http-semantics_c0509, rfc9110-http-semantics_c0507, rfc9110-http-semantics_c0702, rfc9110-http-semantics_c0519 | Weak validators, Strong validators |
| True | 66.67% | 100.00% | 100.00% | 1056.69 ms | What is the purpose of QUIC immediate close? | rfc9000-quic_c0403, rfc9000-quic_c0406, rfc9000-quic_c0394, rfc9000-quic_c0395, rfc9000-quic_c0405 | CONNECTION_CLOSE, terminate |
