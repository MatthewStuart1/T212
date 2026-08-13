"""
TradingView -> Trading 212 webhook bridge ("the messenger")
============================================================
Listens for TradingView alerts and places orders on Trading 212.

SAFETY DEFAULTS:
- Points at the DEMO (pretend money) environment
- Requires a secret passphrase in every alert
- Caps order size
- Blocks duplicate orders fired within 60 seconds

Setup:
1. Set two environment variables where you host this:
     T212_API_KEY      = your Trading 212 API key
     WEBHOOK_SECRET    = any long random phrase you invent
2. Deploy (see instructions in chat), get your public URL.
3. In TradingView, point the alert webhook at:  https://YOUR-URL/webhook
"""

import os
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ---------------- SETTINGS ----------------

# DEMO environment = pretend money. When you're ready for real money
# (and only then), change "demo" to "live".
T212_BASE_URL = "https://demo.trading212.com/api/v0"

T212_API_KEY = os.environ.get("T212_API_KEY", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

# Map TradingView symbols to Trading 212 tickers.
# Add each instrument you trade. Find T212's ticker via their
# /equity/metadata/instruments endpoint or the app.
TICKER_MAP = {
    "AAPL": "AAPL_US_EQ",
    "TSLA": "TSLA_US_EQ",
    # "VOD":  "VODl_EQ",   # example London-listed ticker
}

# Hard safety cap: the most shares any single order may buy/sell.
MAX_QUANTITY = 5

# Ignore a repeat signal for the same ticker within this many seconds.
DUPLICATE_WINDOW_SECONDS = 60

# ------------------------------------------

last_order_time = {}  # ticker -> timestamp of last order


def reject(reason, code=400):
    """Log the rejection reason so it shows up in Render logs."""
    print(f"REJECTED ({code}): {reason}")
    return jsonify({"error": reason}), code


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    print(f"INCOMING ALERT: {request.data[:500]}")  # raw payload, for debugging
    if not data:
        return reject("no JSON received - check the alert Message box is valid JSON")

    # 1. Check the secret passphrase
    if data.get("secret") != WEBHOOK_SECRET or not WEBHOOK_SECRET:
        return reject("wrong or missing secret", 403)

    # 2. Read the alert
    tv_ticker = str(data.get("ticker", "")).upper()
    action = str(data.get("action", "")).lower()   # "buy" or "sell"
    try:
        quantity = float(data.get("qty", 0))
    except (TypeError, ValueError):
        return reject("qty must be a number")

    # 3. Validate
    if action not in ("buy", "sell"):
        return reject(f"action must be buy or sell, got '{action}'")
    if not 0 < quantity <= MAX_QUANTITY:
        return reject(f"qty must be between 0 and {MAX_QUANTITY}, got {quantity}")
    t212_ticker = TICKER_MAP.get(tv_ticker)
    if not t212_ticker:
        return reject(f"unknown ticker '{tv_ticker}' - add it to TICKER_MAP")

    # 4. Block rapid duplicates (protects against webhook retries)
    now = time.time()
    if now - last_order_time.get(t212_ticker, 0) < DUPLICATE_WINDOW_SECONDS:
        return jsonify({"skipped": "duplicate signal within window"}), 200

    # 5. Place the market order (negative quantity = sell)
    signed_qty = quantity if action == "buy" else -quantity
    resp = requests.post(
        f"{T212_BASE_URL}/equity/orders/market",
        headers={"Authorization": T212_API_KEY},
        json={"ticker": t212_ticker, "quantity": signed_qty},
        timeout=15,
    )

    if resp.status_code in (200, 201):
        last_order_time[t212_ticker] = now
        print(f"ORDER PLACED: {action} {quantity} {t212_ticker}")
        return jsonify({"ok": True, "t212_response": resp.json()}), 200

    print(f"ORDER FAILED ({resp.status_code}): {resp.text}")
    return jsonify({"error": "Trading 212 rejected the order",
                    "status": resp.status_code,
                    "detail": resp.text}), 502


@app.route("/", methods=["GET"])
def health():
    return "Bridge is running", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
TradingView -> Trading 212 webhook bridge ("the messenger")
============================================================
Listens for TradingView alerts and places orders on Trading 212.

SAFETY DEFAULTS:
- Points at the DEMO (pretend money) environment
- Requires a secret passphrase in every alert
- Caps order size
- Blocks duplicate orders fired within 60 seconds

Setup:
1. Set two environment variables where you host this:
     T212_API_KEY      = your Trading 212 API key
     WEBHOOK_SECRET    = any long random phrase you invent
2. Deploy (see instructions in chat), get your public URL.
3. In TradingView, point the alert webhook at:  https://YOUR-URL/webhook
"""

import os
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ---------------- SETTINGS ----------------

# DEMO environment = pretend money. When you're ready for real money
# (and only then), change "demo" to "live".
T212_BASE_URL = "https://demo.trading212.com/api/v0"

T212_API_KEY = os.environ.get("T212_API_KEY", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

# Map TradingView symbols to Trading 212 tickers.
# Add each instrument you trade. Find T212's ticker via their
# /equity/metadata/instruments endpoint or the app.
TICKER_MAP = {
    "AAPL": "AAPL_US_EQ",
    "TSLA": "TSLA_US_EQ",
    # "VOD":  "VODl_EQ",   # example London-listed ticker
}

# Hard safety cap: the most shares any single order may buy/sell.
MAX_QUANTITY = 5

# Ignore a repeat signal for the same ticker within this many seconds.
DUPLICATE_WINDOW_SECONDS = 60

# ------------------------------------------

last_order_time = {}  # ticker -> timestamp of last order


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "no JSON received"}), 400

    # 1. Check the secret passphrase
    if data.get("secret") != WEBHOOK_SECRET or not WEBHOOK_SECRET:
        return jsonify({"error": "wrong or missing secret"}), 403

    # 2. Read the alert
    tv_ticker = str(data.get("ticker", "")).upper()
    action = str(data.get("action", "")).lower()   # "buy" or "sell"
    try:
        quantity = float(data.get("qty", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "qty must be a number"}), 400

    # 3. Validate
    if action not in ("buy", "sell"):
        return jsonify({"error": "action must be buy or sell"}), 400
    if not 0 < quantity <= MAX_QUANTITY:
        return jsonify({"error": f"qty must be between 0 and {MAX_QUANTITY}"}), 400
    t212_ticker = TICKER_MAP.get(tv_ticker)
    if not t212_ticker:
        return jsonify({"error": f"unknown ticker {tv_ticker} - add it to TICKER_MAP"}), 400

    # 4. Block rapid duplicates (protects against webhook retries)
    now = time.time()
    if now - last_order_time.get(t212_ticker, 0) < DUPLICATE_WINDOW_SECONDS:
        return jsonify({"skipped": "duplicate signal within window"}), 200

    # 5. Place the market order (negative quantity = sell)
    signed_qty = quantity if action == "buy" else -quantity
    resp = requests.post(
        f"{T212_BASE_URL}/equity/orders/market",
        headers={"Authorization": T212_API_KEY},
        json={"ticker": t212_ticker, "quantity": signed_qty},
        timeout=15,
    )

    if resp.status_code in (200, 201):
        last_order_time[t212_ticker] = now
        print(f"ORDER PLACED: {action} {quantity} {t212_ticker}")
        return jsonify({"ok": True, "t212_response": resp.json()}), 200

    print(f"ORDER FAILED ({resp.status_code}): {resp.text}")
    return jsonify({"error": "Trading 212 rejected the order",
                    "status": resp.status_code,
                    "detail": resp.text}), 502


@app.route("/", methods=["GET"])
def health():
    return "Bridge is running", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
