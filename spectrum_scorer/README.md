# Spectrum Scorer

Spectrum-based fault localization library for root cause analysis.

## Formulas Supported

- **Ochiai**: Best general-purpose SBFL formula. Score = n_ef / sqrt(n_f * n_e)
- **Tarantula**: Classic formula from initial SBFL research
- **Jaccard**: Simple overlap coefficient
- **DStar**: High recall formula, good when suspects are rare

## Installation

```bash
pip install spectrum-scorer
```

## Library API

```python
from spectrum_scorer import Execution, SpectrumScorer

executions = [
    Execution(components=["frontend", "cart", "database"], is_failing=True),
    Execution(components=["frontend", "cart"], is_failing=False),
]

scorer = SpectrumScorer(formula="ochiai")
scores = scorer.score(executions)
ranked = scorer.rank(executions)  # sorted by score descending
```

## CLI

```bash
spectrum-score score --input executions.json
spectrum-score score --input executions.json --formula ochiai
spectrum-score score --input executions.json --output-format json
spectrum-score compare --input executions.json
```

## Input Format (JSON)

```json
{
  "executions": [
    {"components": ["frontend", "cart"], "is_failing": false},
    {"components": ["frontend", "cart", "db"], "is_failing": true}
  ]
}
```

## Quick Test

```python
from spectrum_scorer import Execution, SpectrumScorer

executions = [
    Execution(components=["frontend", "cart", "db"], is_failing=True),
    Execution(components=["frontend", "cart"], is_failing=False),
]
scorer = SpectrumScorer("ochiai")
print(scorer.rank(executions))
```
