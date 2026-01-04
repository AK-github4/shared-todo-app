
from flask import Flask, request, jsonify, render_template, redirect, url_for
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession
from datetime import datetime
import uuid
import os
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ---- Google 認証（Render Secret File 前提。存在しない場合は環境変数でフォールバック） ----
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def make_client():
    """
    Render の Secret Files (/etc/secrets/credentials.json) を最優先で使い、
    見つからない場合は GOOGLE_SERVICE_ACCOUNT_JSON（環境変数）を使います。
    gspread クライアントには AuthorizedSession を渡します。
    """
    secret_path = "/etc/secrets/credentials.json"  # Render Secret Files 標準パス
    creds = None

    if os.path.exists(secret_path):
        # google-auth 経由でサービスアカウント認証
        creds = Credentials.from_service_account_file(secret_path, scopes=SCOPES)
    else:
        # フォールバック：環境変数に JSON 本文がある場合
        json_text = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not json_text:
            raise FileNotFoundError(
                "Service Account JSON が見つかりません。/etc/secrets/credentials.json "
                "または環境変数 GOOGLE_SERVICE_ACCOUNT_JSON を設定してください。"
            )
        from json import loads
        info = loads(json_text)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)

    # 認可セッション（Requests セッション）を作成
    session = AuthorizedSession(creds)
    # 必要に応じて session.verify にカスタム CA を指定可能（通常は不要）
    # session.verify = "/path/to/corp-root.pem"

    # gspread クライアントへ認証＆セッションを渡す
    gc = gspread.Client(auth=creds, session=session)  # service_account と同等の認証経路です。[6](https://docs.gspread.org/en/v3.7.0/api.html)
    return gc

gc = make_client()

# ---- Spreadsheet を開く（ID優先、なければタイトル） ----
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")  # 任意（Render の Environment で設定可能）
SPREADSHEET_TITLE = os.environ.get("SPREADSHEET_TITLE", "shared_todo")

if SPREADSHEET_ID:
    sh = gc.open_by_key(SPREADSHEET_ID)  # IDで開くのが衝突に強く推奨。[5](https://docs.gspread.org/en/latest/user-guide.html)
else:
    sh = gc.open(SPREADSHEET_TITLE)

sheet = sh.sheet1  # 先頭のシートを使用。[5](https://docs.gspread.org/en/latest/user-guide.html)

# ---- 初期化：ヘッダーが無い場合は作成（安全運用向け） ----
def ensure_header():
    try:
        header = sheet.row_values(1)
        expected = ["id", "item", "status", "rating", "note", "created_at"]
        if header != expected:
            # 既存ヘッダーが異なる場合は上書き（必要なら手動で合わせてください）
            sheet.update([expected], "A1:F1")  # gspread v6 の update 仕様に合わせています。[4](https://pypi.org/project/gspread/)
    except Exception as e:
        app.logger.warning(f"Header check failed: {e}")

ensure_header()

# -------------------------
# Web UI
# -------------------------
@app.route("/")
def index():
    records = sheet.get_all_records()  # [{id, item, status, rating, note, created_at}, ...]
    # created_at が空の場合も文字列化して安全にソート
    def _sort_key(row):
        return str(row.get("created_at") or "")
    records = sorted(records, key=_sort_key, reverse=True)
    return render_template("index.html", records=records)

@app.route("/add_web", methods=["POST"])
def add_web():
    item = (request.form.get("item") or "").strip()
    rating = (request.form.get("rating") or "").strip()  # "1"〜"5" or ""
    note = (request.form.get("note") or "").strip()      # 空OK

    rating_val = int(rating) if rating.isdigit() else ""
    row_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    # 列順：id, item, status, rating, note(E), created_at(F)
    sheet.append_row([row_id, item, "未完了", rating_val, note, created_at])
    return redirect(url_for("index"))

# -------------------------
# 削除（ID指定）
# -------------------------
@app.route("/delete/<row_id>", methods=["POST"])
def delete_item(row_id):
    try:
        cell = sheet.find(row_id)     # ID（A列）で検索
        sheet.delete_rows(cell.row)   # 1行削除
    except gspread.exceptions.CellNotFound:
        app.logger.info(f"ID not found (already deleted?): {row_id}")
    return redirect(url_for("index"))

# -------------------------
# API（任意：LINE Bot 等からも利用可能）
# -------------------------
@app.route("/add", methods=["POST"])
def add_item():
    data = request.json or {}
    item = (data.get("item") or "").strip()
    rating = data.get("rating")      # 1〜5（数値想定、未指定可）
    note = (data.get("note") or "").strip()

    row_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    sheet.append_row([row_id, item, "未完了", rating, note, created_at])
    return jsonify({"status": "ok", "id": row_id, "item": item, "rating": rating, "note": note})

if __name__ == "__main__":
    # ローカルでのデバッグ用（Render では gunicorn で起動）
    app.run(host="0.0.0.0", port=5000, debug=True)
