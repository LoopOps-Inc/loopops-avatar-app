#!/usr/bin/env python
"""Export the OpenAPI 3.1 documents (one per role) to a directory.

Thin wrapper around ``python -m actinver_agent.cli export-openapi``. The
generated schema is the API contract of record (docs/04-backend/04 §0); the
mobile/web client types are generated from it.
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/openapi")
    args = parser.parse_args()
    cmd = [sys.executable, "-m", "actinver_agent.cli", "export-openapi", "--out", args.out]
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
