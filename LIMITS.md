# SKEPTID: Limitations and Honest Framing

## Core Principles
1. **Risk Score, Not Proof**: SKEPTID produces calibrated risk scores with observable evidence indicators. It does not provide absolute proof of authenticity or malicious intent.
2. **Generalization Boundaries**:
   - Machine learning and heuristic forensic detectors are subject to evasion by novel generators, heavy recompression, or adversarial perturbations.
   - Out-of-distribution generators may exhibit features distinct from the training distribution.
3. **Fusion Heuristics**:
   - Multi-signal fusion weights (such as email text, URL, header, and attachment contributions) are rule-based heuristics calibrated on validation data.
   - Floor rules prioritize high-severity signals (e.g. verified malicious links or known threat triggers) but may yield elevated risk in benign anomaly cases.
4. **Pretrained Encoders**:
   - Any engine utilizing pretrained encoders or checkpoints is documented as utilizing transfer features and not labeled "trained from scratch".
5. **No Fabricated Certainty**:
   - When models or providers disagree (`max(risk) - min(risk) > 0.40`), disagreement is flagged and confidence is explicitly reduced.
   - If all providers fail, a 503 error is returned rather than generating a fallback verdict.
