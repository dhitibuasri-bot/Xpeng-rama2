from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

import fitz
import os
import json
import gspread
import re
import io

from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)

# =========================
# GOOGLE SHEET CONFIGURATION
# =========================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
google_creds_raw = os.environ.get("GOOGLE_CREDENTIALS")
if google_creds_raw:
    try:
        google_creds = json.loads(google_creds_raw)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
        client = gspread.authorize(creds)
        sheet = client.open("XPENG Referral").sheet1
    except:
        sheet = None
else:
    sheet = None

# 🟢 ปรับลดรุ่นรถตามบรีฟ เหลือเฉพาะ G6, X9_2026 และ SCREEN (การตั้งค่าที่ใช้บ่อย)
# 🟢 ปรับเปลี่ยนชื่อไฟล์ชี้เป้าตามโฟลเดอร์ใหม่ของน้าดิษ
PDFS = {
    "G6": "manuals/G6.pdf",
    "X9_2026": "manuals/X9_2026.pdf",
    "SCREEN": "manuals/frequent_settings.pdf"  # ชี้ไปที่ไฟล์ชื่อใหม่เรียบร้อยครับ
}

pdf_data = []

def load_pdf_manuals():
    global pdf_data
    if pdf_data: return
    for model, path in PDFS.items():
        if model == "SCREEN" or not os.path.exists(path): continue
        try:
            doc = fitz.open(path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text("text", sort=True)
                text = re.sub(r'([ก-๙])\s+([่้๊๋ัิีึืุู็์ำ])', r'\1\2', text)
                pdf_data.append({"model": model, "page": page_num + 1, "text": text})
        except Exception as e:
            print(e)

@app.route("/")
def home():
    return send_file("index.html")

@app.route("/search", methods=["POST"])
def search():
    try:
        load_pdf_manuals()
        data = request.json or {}
        query = data.get("query", "").strip()
        model = data.get("model", "")
        if not model or model == "SCREEN" or not query: return jsonify([])

        results = []
        clean_query = re.sub(r'\s+', '', query.lower())

        for item in pdf_data:
            if item["model"] != model: continue
            clean_text = re.sub(r'\s+', '', item["text"].lower())

            if clean_query in clean_text:
                results.append({
                    "model": item["model"],
                    "page": item["page"],
                    "text": item["text"]
                })
        return jsonify(results[:10])
    except:
        return jsonify([]), 500

@app.route("/view_chunk/<model>/<int:page>")
def view_pdf_chunk(model, page):
    pdf_path = PDFS.get(model)
    if not pdf_path or not os.path.exists(pdf_path): return "Not Found", 404

    try:
        src_doc = fitz.open(pdf_path)
        total_pages = len(src_doc)
        
        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        
        dest_doc = fitz.open()
        dest_doc.insert_pdf(src_doc, from_page=start_page - 1, to_page=end_page - 1)
        
        pdf_stream = io.BytesIO()
        dest_doc.save(pdf_stream)
        pdf_stream.seek(0)
        
        src_doc.close()
        dest_doc.close()
        
        return send_file(pdf_stream, mimetype="application/pdf")
    except:
        return "Error loading snippet", 500

# ⚡ ฟังก์ชันสำหรับดึงไฟล์เต็มเล่ม (ใช้สำหรับเปิดหน้าจอ SCREEN ทันที)
@app.route("/view/<model>")
def view_pdf(model):
    pdf_path = PDFS.get(model)
    if not pdf_path or not os.path.exists(pdf_path): return "Not Found", 404
    return send_file(pdf_path, mimetype="application/pdf")

@app.route("/referral", methods=["POST"])
def referral():
    if not sheet: return jsonify({"success": False}), 500
    data = request.json or {}
    try:
        sheet.append_row([data.get("your_name"), data.get("your_phone"), data.get("friend_name"), data.get("friend_phone"), data.get("model"), data.get("note")])
        return jsonify({"success": True})
    except:
        return jsonify({"success": False}), 500

main = app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)