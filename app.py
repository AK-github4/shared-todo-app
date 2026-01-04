
from flask import Flask, request, jsonify, render_template, redirect, url_for
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import uuid

app = Flask(__name__)

# 認証（RenderのSecret Files／環境変数方式に合わせてパス調整）
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
JSON_PATH = "/etc/secrets/credentials.json"  # 例：Secret Filesを使う場合
creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_PATH, scope)
client = gspread.authorize(creds)
sheet = client.open("shared_todo").sheet1

@app.route("/")
def index():
    records = sheet.get_all_records()  # ヘッダー名に合わせて辞書化
    # 新着順表示（created_atが空なら末尾扱い）
    records = sorted(records, key=lambda x: x.get("created_at", ""), reverse=True)
    return render_template("index.html", records=records)

@app.route("/add_web", methods=["POST"])
def add_web():
    item = request.form["item"].strip()
    rating = request.form.get("rating", "").strip()  # "1"〜"5" or ""
    note = (request.form.get("note") or "").strip()  # ← 新規（空OK）

    rating_val = int(rating) if rating.isdigit() else ""
    row_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    # 列順：id, item, status, rating, note(E), created_at(F)
    sheet.append_row([row_id, item, "未完了", rating_val, note, created_at])
    return redirect(url_for("index"))

@app.route("/delete/<row_id>", methods=["POST"])
def delete_item(row_id):
    cell = sheet.find(row_id)  # A列のIDを検索
    sheet.delete_rows(cell.row)
    return redirect(url_for("index"))

# API側もNoteに対応（任意）
@app.route("/add", methods=["POST"])
def add_item():
    data = request.json or {}
    item = (data.get("item") or "").strip()
    rating = data.get("rating")  # 1〜5（数値）を想定、未指定可
    note = (data.get("note") or "").strip()

    row_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    sheet.append_row([row_id, item, "未完了", rating, note, created_at])
    return jsonify({"status": "ok", "id": row_id, "item": item, "rating": rating, "note": note})

