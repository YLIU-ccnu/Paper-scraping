#!/usr/bin/env python3

import os
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml_physics_crawler.scheduler import should_run_scheduled_update


def main() -> int:
    interval_days = int(os.getenv("PAPER_UPDATE_INTERVAL_DAYS", "5"))
    output_file = os.getenv("PAPER_OUTPUT_FILE", str(ROOT / "results" / "papers.csv"))
    python_bin = os.getenv("PYTHON_BIN", sys.executable)
    extra_args = shlex.split(os.getenv("PAPER_EXTRA_ARGS", ""))

    if not should_run_scheduled_update(output_file, interval_days):
        print(f"Scheduled update skipped: interval {interval_days} days has not elapsed yet.")
        return 0

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    command = [
        python_bin,
        str(ROOT / "paper_scraping.py"),
        "--source",
        "arxiv",
        "--crawl-mode",
        "incremental",
        "--no-total-limit",
        "--output-format",
        "csv",
        "--output-file",
        output_file,
        *extra_args,
    ]

    print("Running scheduled update:")
    print(" ".join(shlex.quote(part) for part in command))
    subprocess.run(command, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
