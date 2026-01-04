from flask import Flask, request, jsonify, render_template, redirect, url_for
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession
from datetime import datetime
import uuid
import os
import logging
import json

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# -------------------------
# Google 認証
# -------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def make_client():
    secret_path = "/etc/secrets/credentials.json"
    creds = None

    if os.path.exists(secret_path):
        creds = Credentials.from_service_account_file(secret_path, scopes=SCOPES)
    else:
        json_text = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not json_text:
            raise RuntimeError("Service Account JSON が見つかりません")
        info = json.loads(json_text)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)

    session = AuthorizedSession(creds)
    return gspread.Client(auth=creds, session=session)

gc = make_client()

# -------------------------
# Spreadsheet
# -------------------------
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
SPREADSHEET_TITLE = os.environ.get("SPREADSHEET_TITLE", "shared_todo")

if SPREADSHEET_ID:
    sh = gc.open_by_key(SPREADSHEET_ID)
else:
    sh = gc.open(SPREADSHEET_TITLE)

sheet = sh.sheet1

# -------------------------
# 初期ヘッダー保証
# -------------------------
def ensure_header():
    expected = ["id", "item", "status", "rating", "note", "created_at"]
    try:
        header = sheet.row_values(1)
        if header != expected:
            sheet.update("A1:F1", [expected])
    except Exception as e:
        app.logger.warning(f"Header check failed: {e}")

ensure_header()

# -------------------------
# Web UI
# -------------------------
@app.route("/")
def index():
    records = sheet.get_all_records()

    records = sorted(
        records,
        key=lambda r: str(r.get("created_at") or ""),
        reverse=True
    )

    return render_template("index.html", records=records)

# -------------------------
# Web 追加（HTML form）
# -------------------------
@app.route("/add_web", methods=["POST"])
def add_web():
    item = (request.form.get("item") or "").strip()
    rating = (request.form.get("rating") or "").strip()
    note = (request.form.get("note") or "").strip()

    if not item:
        return redirect(url_for("index"))

    rating_val = int(rating) if rating.isdigit() else ""

    row_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    sheet.append_row([
        row_id,
        item,
        "未完了",
        rating_val,
        note,
        created_at
    ])

    return redirect(url_for("index"))

# -------------------------
# 削除（Web）
# -------------------------
@app.route("/delete/<row_id>", methods=["POST"])
def delete_item(row_id):
    try:
        cell = sheet.find(row_id)
        sheet.delete_rows(cell.row)
    except gspread.exceptions.CellNotFound:
        app.logger.info(f"ID not found: {row_id}")

    return redirect(url_for("index"))

# -------------------------
# API（JSON専用）
# -------------------------
@app.route("/add", methods=["POST"])
def add_item():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON required"}), 400

    item = (data.get("item") or "").strip()
    rating = data.get("rating")
    note = (data.get("note") or "").strip()

    if not item:
        return jsonify({"error": "item required"}), 400

    rating_val = int(rating) if isinstance(rating, int) else ""

    row_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    sheet.append_row([
        row_id,
        item,
        "未完了",
        rating_val,
        note,
        created_at
    ])

    return jsonify({
        "status": "ok",
        "id": row_id,
        "item": item,
        "rating": rating_val,
        "note": note
    })

# -------------------------
# ローカル起動用
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
