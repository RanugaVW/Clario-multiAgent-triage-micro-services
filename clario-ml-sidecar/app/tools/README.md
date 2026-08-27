# Agent Tools

## Redaction Tool

`redaction_tool.py` is the runtime redaction component used on incoming tickets before they are passed to downstream models. It is distinct from `ml_finetuning/src/distillation/pii_clean.py`, which performs a one-time cleaning pass over offline training data.
