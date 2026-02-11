#!/usr/bin/env python3
# Enhanced Redeemer
# - Deletes captcha image after entry
# - Lock file (script name + PID)
# - Prevents duplicate instances
# - Runtime log file
# - Redeem history (ID + code tracking)

import os
import sys
import json
import time
import signal
import random
import hashlib
import requests
import argparse
import csv
import subprocess
from pathlib import Path
from datetime import datetime

# ===============================
# PATHS
# ===============================

SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
SCRIPT_NAME = SCRIPT_PATH.stem

LOCK_FILE = SCRIPT_DIR / f"{SCRIPT_NAME}.lock"  # lock file includes script name
REDEEM_LOG_FILE = SCRIPT_DIR / f"{SCRIPT_NAME}_redeem_history.json"
RUNTIME_LOG_FILE = SCRIPT_DIR / f"{SCRIPT_NAME}_runtime.log"

LOGIN_URL = "https://wos-giftcode-api.centurygame.com/api/player"
CAPTCHA_URL = "https://wos-giftcode-api.centurygame.com/api/captcha"
REDEEM_URL = "https://wos-giftcode-api.centurygame.com/api/gift_code"
WOS_ENCRYPT_KEY = "tB87#kPtkxqOS2"

EXPECTED_CAPTCHA_LENGTH = 4
VALID_CHARACTERS = set("123456789ABCDEFGHIJKLMNPQRSTUVWXYZ")
DELAY = 1

# ===============================
# LOGGING
# ===============================

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} - {message}"
    print(line)
    with open(RUNTIME_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ===============================
# LOCK FILE
# ===============================

def create_lock():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_pid = os.getpid()

    if LOCK_FILE.exists():
        try:
            with open(LOCK_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                old_pid = data.get("pid")
                started = data.get("started")

            # Check if process still exists
            os.kill(old_pid, 0)
            print(f"Script already running (PID {old_pid}, started {started}).")
            choice = input("Stop old process? (y/n): ").strip().lower()
            if choice == "y":
                os.kill(old_pid, signal.SIGTERM)
                time.sleep(1)
            else:
                sys.exit(0)

        except Exception:
            # Stale lock
            print("Stale lock detected. Replacing lock file.")

    lock_data = {
        "pid": current_pid,
        "started": now
    }

    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(lock_data, f, indent=2)

def remove_lock():
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()



# ===============================
# HISTORY (Full ID+Code Tracking)
# ===============================

def load_history():
    if REDEEM_LOG_FILE.exists():
        with open(REDEEM_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "checked": {},      # { "ID|CODE": {status, timestamp} }
        "inactive_codes": []  # expired / inactive codes
    }

def save_history(history):
    with open(REDEEM_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def pair_key(fid, code):
    return f"{fid}|{code}"


# ===============================
# HELPERS
# ===============================

def encode_data(data):
    secret = WOS_ENCRYPT_KEY
    sorted_keys = sorted(data.keys())
    encoded = "&".join([f"{k}={data[k]}" for k in sorted_keys])
    sign = hashlib.md5(f"{encoded}{secret}".encode()).hexdigest()
    return {"sign": sign, **data}

def post(url, payload):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    return requests.post(url, data=payload, headers=headers, timeout=15)

# ===============================
# MANUAL CAPTCHA
# ===============================

def fetch_manual_captcha(fid):
    payload = encode_data({
        "fid": fid,
        "time": int(time.time() * 1000),
        "init": "0"
    })

    r = post(CAPTCHA_URL, payload)
    if r.status_code != 200:
        return None

    data = r.json()
    img_base64 = data.get("data", {}).get("img")
    if not img_base64:
        return None

    import base64
    img_bytes = base64.b64decode(img_base64.split(",")[-1])
    temp_path = SCRIPT_DIR / f"captcha_{fid}.png"

    with open(temp_path, "wb") as f:
        f.write(img_bytes)

    subprocess.run(["termux-open", str(temp_path)], check=False)

    captcha_text = input("Enter captcha (4 chars): ").strip().upper()

    # Delete image immediately after entry
    if temp_path.exists():
        temp_path.unlink()

    if len(captcha_text) == EXPECTED_CAPTCHA_LENGTH and \
       all(c in VALID_CHARACTERS for c in captcha_text):
        return captcha_text

    return None

# ===============================
# REDEEM
# ===============================


def redeem(fid, code, history):

    key = pair_key(fid, code)

    # Skip inactive/expired codes
    if code in history.get("inactive_codes", []):
        log(f"SKIP | ID={fid} | CODE={code} | Code inactive")
        return

    # Skip already checked pairs
    if key in history.get("checked", {}):
        log(f"SKIP | ID={fid} | CODE={code} | Already checked ({history['checked'][key]['status']})")
        return

    log(f"ATTEMPT | ID={fid} | CODE={code}")

    login_payload = encode_data({
        "fid": fid,
        "time": int(time.time() * 1000)
    })

    login_resp = post(LOGIN_URL, login_payload)
    if login_resp.status_code != 200:
        status = "LOGIN_FAILED"
        history["checked"][key] = {
            "status": status,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_history(history)
        log(f"CHECKED | ID={fid} | CODE={code} | RESULT={status}")
        return

    captcha_code = fetch_manual_captcha(fid)
    if not captcha_code:
        status = "CAPTCHA_FAILED"
        history["checked"][key] = {
            "status": status,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_history(history)
        log(f"CHECKED | ID={fid} | CODE={code} | RESULT={status}")
        return

    redeem_payload = encode_data({
        "fid": fid,
        "cdk": code,
        "captcha_code": captcha_code,
        "time": int(time.time() * 1000)
    })

    redeem_resp = post(REDEEM_URL, redeem_payload)
    if redeem_resp.status_code != 200:
        status = "REQUEST_FAILED"
        history["checked"][key] = {
            "status": status,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_history(history)
        log(f"CHECKED | ID={fid} | CODE={code} | RESULT={status}")
        return

    result = redeem_resp.json().get("msg", "")
    status = result

    # Mark expired / inactive codes globally
    if result in ["TIME ERROR", "Code has expired"]:
        history.setdefault("inactive_codes", []).append(code)

    history["checked"][key] = {
        "status": status,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    save_history(history)

    log(f"CHECKED | ID={fid} | CODE={code} | RESULT={status}")


# ===============================
# LOAD IDS
# ===============================

def load_ids(path):
    ids = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            for item in row:
                if item.strip().isdigit():
                    ids.append(item.strip())
    return sorted(set(ids), key=int)

# ===============================
# MAIN
# ===============================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--code", required=True)
    args = parser.parse_args()

    create_lock()

    try:
        history = load_history()
        ids = load_ids(args.csv)

        log(f"Loaded {len(ids)} IDs")

        for fid in ids:
            redeem(fid, args.code, history)
            time.sleep(DELAY + random.uniform(0, 0.5))

    finally:
        remove_lock()

if __name__ == "__main__":
    main()
