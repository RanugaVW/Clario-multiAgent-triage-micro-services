# Clario

Clario is a multi agentic customer-support ticket platform with a web frontend, API gateway, agent orchestration service, model fine-tuning workflow, and vector-store knowledge base.

## Repository structure

```text
clario/
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── frontend/                         # Member 3
│   ├── src/
│   │   ├── features/
│   │   │   ├── ticket-submission/
│   │   │   │   ├── components/
│   │   │   │   ├── hooks/
│   │   │   │   ├── api.ts
│   │   │   │   └── types.ts
│   │   │   ├── agent-review/
│   │   │   │   ├── components/
│   │   │   │   ├── hooks/
│   │   │   │   ├── api.ts
│   │   │   │   └── types.ts
│   │   │   └── auth/
│   │   ├── shared/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── Dockerfile
│   ├── package.json
│   └── README.md
├── api_gateway/                      # Member 3
│   ├── app/
│   │   ├── auth/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── routers/
│   │   └── main.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
├── agent_orchestration/              # Member 2
│   ├── app/
│   │   ├── agents/
│   │   │   ├── billing_agent/
│   │   │   ├── shared/
│   │   │   └── technical_agent/
│   │   ├── graph/
│   │   │   ├── handoff_node.py
│   │   │   ├── routing_node.py
│   │   │   ├── state.py
│   │   │   ├── supervisor_node.py
│   │   │   └── validation_node.py
│   │   ├── tools/
│   │   │   ├── classification_tool.py
│   │   │   ├── rag_tool.py
│   │   │   └── redaction_tool.py
│   │   └── main.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
├── ml_finetuning/                    # Member 1
│   ├── data/
│   │   ├── raw/                      # Local ticket data; ignored by Git
│   │   ├── distilled/
│   │   └── splits/
│   ├── notebooks/
│   ├── src/
│   │   ├── distillation/
│   │   ├── evaluation/
│   │   ├── inference/
│   │   └── training/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
├── vector_store/                     # Member 2
│   ├── kb_documents/                 # Local knowledge-base documents; ignored by Git
│   ├── build_index.py
│   └── README.md
├── infra/                            # Member 3
│   ├── nginx/
│   └── postgres/
│       └── init.sql
├── scripts/
│   └── seed_demo_data.py
└── docs/
    ├── architecture_diagram.png
    ├── evaluation_report.md
    └── proposal.pdf
```

## Data handling

Place the original ticket dataset in `ml_finetuning/data/raw/`. This directory is excluded from Git so real customer-support data is not committed.
