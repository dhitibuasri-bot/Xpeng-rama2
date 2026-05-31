from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

import fitz
import os
import json
import gspread
import re

from oauth2client.service_account import ServiceAccountCredentials

# =========================
# APP
# =========================

app = Flask(
    __name__,
    static_folder='static',
    static_url_path='/static'
)

CORS(app)

# =========================
# GOOGLE SHEET
# =========================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

google_creds = json.loads(
    os.environ["GOOGLE_CREDENTIALS"]
)

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    google_creds,
    scope
)

client = gspread.authorize(creds)

sheet = client.open(
    "XPENG Referral"
).sheet1

# =========================
# PDF PATH
# =========================

PDFS = {
    "G6": "manuals/G6.pdf",
    "X9": "manuals/X9.pdf",
    "X9_2026": "manuals/X9_2026.pdf",
    "SCREEN": "manuals/SCREEN.pdf"
}

# =========================
# PDF DATA
# =========================

pdf_data = []

# =========================
# LOAD PDF
# =========================

print("\n🔥 Loading PDF manuals...\n")

for model, path in PDFS.items():

    print(f"📄 Loading {path}")

    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        continue

    doc = fitz.open(path)

    for page_num in range(len(doc)):

        page = doc.load_page(page_num)

        # ดึงข้อความแบบเรียงลำดับ
        text = page.get_text("text", sort=True)

        # แก้ปัญหาสระลอย / วรรณยุกต์ลอย
        text = re.sub(
            r'([ก-๙])\s+([่้๊๋ัิีึืุู็์ำ])',
            r'\1\2',
            text
        )

        pdf_data.append({
            "model": model,
            "page": page_num + 1,
            "text": text
        })

print("\n✅ PDF Loaded Successfully\n")

# =========================
# HOME
# =========================

@app.route("/")
def home():

    return send_file("index.html")

# =========================
# SEARCH
# =========================

@app.route("/search", methods=["POST"])
def search():

    data = request.json

    query = data.get("query", "").strip()

    model = data.get("model", "")

    results = []

    clean_query = re.sub(
        r'\s+',
        '',
        query.lower()
    )

    for item in pdf_data:

        if item["model"] != model:
            continue

        clean_text = re.sub(
            r'\s+',
            '',
            item["text"].lower()
        )

        if clean_query in clean_text:

            snippet = item["text"][:1200]

            results.append({
                "model": item["model"],
                "page": item["page"],
                "text": snippet
            })

    return jsonify(results[:10])

# =========================
# VIEW PDF
# =========================

@app.route("/view/<model>")
def view_pdf(model):

    pdf_path = PDFS.get(model)

    if not pdf_path:
        return "PDF Not Found"

    return send_file(
        pdf_path,
        mimetype="application/pdf"
    )

# =========================
# REFERRAL
# =========================

@app.route("/referral", methods=["POST"])
def referral():

    data = request.json

    try:

        sheet.append_row([
            data.get("your_name"),
            data.get("your_phone"),
            data.get("friend_name"),
            data.get("friend_phone"),
            data.get("model"),
            data.get("note")
        ])

        return jsonify({
            "success": True
        })

    except Exception as e:

        print("❌ ERROR:", e)

        return jsonify({
            "success": False,
            "error": str(e)
        })

# =========================
# RUN
# =========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )