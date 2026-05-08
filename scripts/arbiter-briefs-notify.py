#!/usr/bin/env python3
"""
Arbiter WhatsApp Notification Script

Runs the full Arbiter pipeline and sends a WhatsApp ping when complete.

Usage:
    python3 scripts/arbiter-briefs-notify.py

This script is designed to be run by Hermes cron jobs. It:
1. Runs the full daily report pipeline (collect → generate)
2. Reads the generated report to extract the date
3. Prints the WhatsApp notification message to stdout

The cron job should have:
  script: "scripts/arbiter-briefs-notify.py"
  deliver: "whatsapp:19412234936@s.whatsapp.net"
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
LATEST_REPORT_PATH = REPO_ROOT / "data" / "reports" / "generated" / "latest.json"


def run_command(cmd: list[str], cwd: Path = None) -> str:
    """Run a command and return stdout. Raises on non-zero exit."""
    result = subprocess.run(
        cmd,
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def main():
    # Step 1: Run the daily report pipeline
    # This runs collect_kalshi_public_snapshot.py, collect_polling_evidence.py, and generate_daily_report.ts
    try:
        run_command(["node", "--import", "tsx", "scripts/run_daily_report.ts"])
    except subprocess.CalledProcessError as e:
        print(f"Pipeline failed: {e.stderr}", file=sys.stderr)
        sys.exit(1)

    # Step 2: Read the generated report to get the date
    try:
        with open(LATEST_REPORT_PATH, "r") as f:
            report = json.load(f)
        report_date_str = report.get("reportDate", "")
    except Exception as e:
        print(f"Failed to read report: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 3: Format the date for the WhatsApp message
    try:
        report_date = datetime.fromisoformat(report_date_str)
        # Format: Thursday May 7th, 2026
        day = report_date.day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]
        formatted_date = report_date.strftime(f"%A %B {day}{suffix}, %Y")
    except Exception:
        # Fallback to raw date string if parsing fails
        formatted_date = report_date_str

    # Step 4: Print the WhatsApp message (this gets delivered by the cron job)
    message = f"Arbiter Political briefs for {formatted_date} complete."
    print(message)


if __name__ == "__main__":
    main()
