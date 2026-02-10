#!/usr/bin/env python3
"""
Wrapper for justncodes/wos-giftcode redeem_codes.py
Adds dependency checks before running the redeemer.

USAGE
-----
python redeem_with_checks.py --code CODE --csv ids.txt
"""

# ==========================
# Requirements check (REDEEMER)
# ==========================
import sys, importlib.util

REQUIRED = [
    ("requests", "requests"),
    ("numpy", "numpy"),
    # ("PIL", "pillow"), #OCR
    # ("opencv-python", "opencv-python"),
    ("colorama", "colorama"),
    # ("ddddocr", "ddddocr==1.5.6"), #OCR
]

missing = []
for import_name, pip_name in REQUIRED:
    if importlib.util.find_spec(import_name) is None:
        missing.append(pip_name)

if missing:
    print("\nMissing Python packages for REDEEMER.")
    print("Run:\n")
    print(f"pip install {' '.join(missing)} --ignore-requires-python")
    sys.exit(1)

# ==========================
# Safe imports
# ==========================
import argparse
import subprocess
from pathlib import Path

REDEEM_SCRIPT = "redeem_codes.py"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", required=True)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--ocr-method", default="none")
    args = parser.parse_args()
    
    script_dir = Path(__file__).resolve().parent
    redeemer_path = script_dir / "redeem_codes.py"

    if not redeemer_path.exists():
      print("\nERROR: redeem_codes.py not found.")
      print("\nDownload it with:")
      print(
        f"curl -L -o \"{redeemer_path}\" "
        "https://raw.githubusercontent.com/justncodes/wos-giftcode/main/redeem_codes.py"
      )
      print("\nThen rerun the script.")
      sys.exit(1)
    
    subprocess.run(
        [
            sys.executable,
            str(redeemer_path),
            "--code", args.code,
            "--csv", args.csv,
            "--ocr-method", args.ocr_method,
        ],
        check=False,
    )

if __name__ == "__main__":
    main()
