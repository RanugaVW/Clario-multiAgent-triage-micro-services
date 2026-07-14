"""Minimal full-stack smoke test for a running Clario deployment.

Usage: python scripts/e2e_test.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Clario API smoke test.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--health-path", default="/health")
    args = parser.parse_args()
    url = f"{args.base_url.rstrip('/')}{args.health_path}"
    try:
        with urlopen(url, timeout=10) as response:  # noqa: S310 - explicitly supplied test URL
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Health check returned HTTP {response.status}")
    except (HTTPError, URLError, RuntimeError) as error:
        print(f"E2E smoke test failed: {error}", file=sys.stderr)
        return 1
    print(f"E2E smoke test passed: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
