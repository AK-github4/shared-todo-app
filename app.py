from flask import Flask, request, jsonify, render_template, redirect
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)   # ← これが必須！

# Google Sheets 認証
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

sheet = client.open("shared_todo").sheet1

# -------------------------
# Web UI
# -------------------------
@app.route("/")
def index():
    records = sheet.get_all_records()
    return render_template("index.html", records=records)

@app.route("/add_web", methods=["POST"])
def add_web():
    item = request.form["item"]
    sheet.append_row([item, "未完了"])
    return redirect("/")

# -------------------------
# API（LINE Bot でも使える）
# -------------------------
@app.route("/add", methods=["POST"])
def add_item():
    data = request.json
    item = data.get("item")
    sheet.append_row([item, "未完了"])
    return jsonify({"status": "ok", "item": item})

@app.route("/list", methods=["GET"])
def list_items():
    records = sheet.get_all_records()
    return jsonify(records)

if __name__ == "__main__":
    app.run(debug=True)
