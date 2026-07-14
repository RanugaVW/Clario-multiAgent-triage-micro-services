"""Entry point for agent-behaviour evaluations in LangSmith.

Set LANGSMITH_API_KEY and replace `run_evaluation` once the orchestration graph has
an invokable entry point. Keeping the integration boundary here avoids coupling the
application runtime to evaluation-only configuration.
"""

from __future__ import annotations

import os


def run_evaluation() -> None:
    if not os.getenv("LANGSMITH_API_KEY"):
        raise RuntimeError("LANGSMITH_API_KEY must be set before running LangSmith evaluations.")
    raise NotImplementedError("Connect this evaluator after the orchestration graph is implemented.")


if __name__ == "__main__":
    run_evaluation()
