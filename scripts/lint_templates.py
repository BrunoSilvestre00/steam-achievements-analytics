"""Lint Jinja templates through djLint's stdin mode.

Using stdin keeps the hook reliable on Windows, where djLint's directory
scanner may require process spawning that is unavailable in restricted shells.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    templates_dir = Path("steam_analytics/templates")
    failures = 0
    for path in sorted(templates_dir.glob("*.html")):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "djlint",
                "-",
                "--stdin-filename",
                str(path),
                "--profile=jinja",
                "--lint",
            ],
            input=path.read_bytes(),
            text=False,
            capture_output=True,
            check=False,
        )
        if result.stdout:
            if result.returncode:
                print(f"{path}: ", end="")
            print(result.stdout.decode("utf-8", errors="replace"), end="")
        if result.stderr:
            print(result.stderr.decode("utf-8", errors="replace"), end="", file=sys.stderr)
        failures += result.returncode != 0
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
