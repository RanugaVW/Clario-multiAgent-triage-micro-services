# Data Distillation and Cleaning

## One-time PII cleaning

`pii_clean.py` masks personally identifiable information in the training dataset before it is stored long-term, distilled, or used for fine-tuning. It is an offline, **one-time dataset-cleaning step**.

It replaces detected data with tokens rather than deleting it:

| PII type | Placeholder |
|---|---|
| Email address | `[EMAIL]` |
| Phone number | `[PHONE]` |
| Credit-card-like 16-digit number | `[CREDIT_CARD]` |
| IPv4 address | `[IP_ADDRESS]` |
| Person name (spaCy `PERSON`) | `[PERSON]` |
| Geographic entity (spaCy `GPE`) | `[LOCATION]` |
| Organisation (spaCy `ORG`) | `[ORG]` |

Install the Python package dependencies, then install the spaCy English model once:

```powershell
python -m pip install -r ml_finetuning/requirements.txt
python -m spacy download en_core_web_sm
```

This module is deliberately separate from the live [runtime Redaction Tool](../../../agent_orchestration/app/tools/README.md#redaction-tool), which masks incoming ticket text at inference time. Do not substitute one for the other.
