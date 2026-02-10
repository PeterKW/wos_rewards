#!/usr/bin/env python3
"""
Scrape ACTIVE Whiteout Survival gift codes from wosrewards.com
Optionally redeem them using redeem_codes.py

USAGE
-----
Scrape only:
  python scrape_and_redeem.py

Scrape + redeem:
  python scrape_and_redeem.py --redeem
"""

# ==========================
# Requirements check (SCRAPER)
# ==========================
import sys, importlib.util

REQUIRED = [
    ("requests", "requests"),
    ("bs4", "beautifulsoup4"),
]

missing = []
for import_name, pip_name in REQUIRED:
    if importlib.util.find_spec(import_name) is None:
        missing.append(pip_name)

if missing:
    print("\nMissing Python packages for SCRAPER.")
    print("Run:\n")
    print(f"pip install {' '.join(missing)}")
    sys.exit(1)

# ==========================
# Safe imports
# ==========================
import argparse
import subprocess
from pathlib import Path
import requests
from bs4 import BeautifulSoup

URL = "https://www.wosrewards.com"
CODES_FILE = "codes.txt"
IDS_FILE = "ids.txt"
REDEEM_SCRIPT = "redeem_with_checks.py"

def scrape_codes():
    r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    lines = [l.strip() for l in soup.get_text("\n").splitlines()]

    codes = []
    in_active = False

    for line in lines:
        if line == "ACTIVE":
            in_active = True
            continue

        if line == "EXPIRED":
            in_active = False
            break  # stop at first EXPIRED section

        if not in_active:
            continue

        # valid code: uppercase, alphanumeric, not the label itself
        if (
            line.isupper()
            and line.isalnum()
            and len(line) >= 5
            and line != "ACTIVE"
        ):
            codes.append(line)

    # Deduplicate while preserving order
    seen = set()
    return [c for c in codes if not (c in seen or seen.add(c))]

def run_redeemer(codes):
    if not Path(IDS_FILE).exists():
        print("ERROR: ids.txt not found")
        sys.exit(1)

    if not Path(REDEEM_SCRIPT).exists():
        print("ERROR: redeem_with_checks.py not found")
        sys.exit(1)

    for code in codes:
        print(f"\n=== Redeeming {code} ===")
        subprocess.run(
            [
                sys.executable,
                REDEEM_SCRIPT,
                "--code", code,
                "--csv", IDS_FILE,
                "--ocr-method", "none",
            ],
            check=False,
        )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--redeem", action="store_true")
    args = parser.parse_args()

    codes = scrape_codes()

    if not codes:
        print("No codes found.")
        return

    print("\nACTIVE CODES:")
    for c in codes:
        print(c)

    with open(CODES_FILE, "w", encoding="utf-8") as f:
        for c in codes:
            f.write(c + "\n")

    print(f"\nSaved to {CODES_FILE}")

    if args.redeem:
        run_redeemer(codes)

if __name__ == "__main__":
    main()
