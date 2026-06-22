from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

import fitz
import os
import json
import gspread
import re
import io

from oauth2client.service_account import ServiceAccountCredentials

# =========================
# APP CONFIGURATION
# =========================

app = Flask(
    __name__,
    static_folder='static',
    static_url_path='/static'
)

CORS(app)

# =========================
# GOOGLE SHEET CONFIGURATION
# =========================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

google_creds_raw = os.environ.get("GOOGLE_CREDENTIALS")
if google_creds_raw:
    try:
        google_creds = json.loads(google_creds_raw)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
        client = gspread.authorize(creds)
        sheet = client.open("XPENG Referral").sheet1
        print("✅ Google Sheets Connected Successfully")
    except Exception as e:
        print(f"❌ Google Sheets Connection Error: {e}")
        sheet = None
else:
    print("⚠️ WARNING: GOOGLE_CREDENTIALS environment variable is not set!")
    sheet = None

# =========================
# PDF PATHS
# =========================

PDFS = {
    "G6": "manuals/G6.pdf",
    "X9": "manuals/X9.pdf",
    "X9_2026": "manuals/X9_2026.pdf",
    "SCREEN": "manuals/SCREEN.pdf"
}

# =========================
# LAZY LOAD PDF MANUALS
# =========================

pdf_data = []

def load_pdf_manuals():
    global pdf_data
    if pdf_data:
        return

    print("\n🔥 Loading PDF manuals into server memory...\n")
    
    for model, path in PDFS.items():
        if model == "SCREEN":
            continue

        print(f"📄 Loading {path}")
        if not os.path.exists(path):
            print(f"⚠️ Skip: File not found -> {path}")
            continue

        try:
            doc = fitz.open(path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text("text", sort=True)
                text = re.sub(r'([ก-๙])\s+([่้๊๋ัิีึืุู็์ำ])', r'\1\2', text)
                
                pdf_data.append({
                    "model": model,
                    "page": page_num + 1,
                    "text": text
                })
        except Exception as e:
            print(f"❌ Error loading data from {path}: {e}")

    print("\n✅ All PDF Manuals Loaded Successfully\n")

# =========================
# WEB ROUTES
# =========================

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

        if not model or model == "SCREEN" or not query:
            return jsonify([])

        results = []
        clean_query = re.sub(r'\s+', '', query.lower())

        for item in pdf_data:
            if item["model"] != model:
                continue

            clean_text = re.sub(r'\s+', '', item["text"].lower())

            if clean_query in clean_text:
                original_text = item["text"]
                match_idx = original_text.lower().find(query.lower())
                
                if match_idx != -1:
                    start_idx = max(0, match_idx - 200)
                    end_idx = min(len(original_text), match_idx + 600)
                    snippet = original_text[start_idx:end_idx]
                    if start_idx > 0: snippet = "..." + snippet
                    if end_idx < len(original_text): snippet = snippet + "..."
                else:
                    snippet = original_text[:800] + "..."

                results.append({
                    "model": item["model"],
                    "page": item["page"],
                    "text": snippet
                })

        return jsonify(results[:10])

    except Exception as e:
        print("❌ Search API System Error:", e)
        return jsonify({"success": False, "error": "Internal Server Error"}), 500


@app.route("/view/<model>")
def view_pdf(model):
    """เส้นทางเดิมสำหรับเปิดไฟล์เต็ม (ใช้กับ SCREEN เล่มสั้น)"""
    pdf_path = PDFS.get(model)
    if not pdf_path or not os.path.exists(pdf_path):
        return "PDF Manual Not Found", 404
    return send_file(pdf_path, mimetype="application/pdf")


# ⚡ ฟังก์ชันใหม่: ตัดเฉพาะหน้าผลลัพธ์และหน้ารอบๆ (-2 และ +2 หน้า) ส่งให้หน้าบ้านเปิดอ่านแบบพริบตาเดียว
@app.route("/view_chunk/<model>/<int:page>")
def view_pdf_chunk(model, page):
    pdf_path = PDFS.get(model)
    if not pdf_path or not os.path.exists(pdf_path):
        return "PDF Manual Not Found", 404

    try:
        src_doc = fitz.open(pdf_path)
        total_pages = len(src_doc)
        
        # คำนวณหาช่วงหน้าที่จะตัด (-2 หน้า และ +2 หน้าจากหน้าปัจจุบัน)
        # ตัวอย่าง: ค้นเจอหน้า 10 ระบบจะตัดหน้า 8, 9, 10, 11, 12 มาให้ดู
        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        
        # สร้างเอกสาร PDF ชิ้นใหม่ใน Memory
        dest_doc = fitz.open()
        
        # ดึงหน้าเฉพาะช่วงที่เลือกจากเล่มหลัก (fitz ใช้เลขหน้าเริ่มจาก 0)
        dest_doc.insert_pdf(src_doc, from_page=start_page - 1, to_page=end_page - 1)
        
        # แปลงไฟล์เป็น Byte Stream เพื่อส่งออกโดยไม่ต้องเขียนไฟล์ลงดิสก์เซิร์ฟเวอร์
        pdf_stream = io.BytesIO()
        dest_doc.save(pdf_stream)
        pdf_stream.seek(0)
        
        src_doc.close()
        dest_doc.close()
        
        # คำนวณหาหน้าเป้าหมายเพื่อให้เบราเซอร์เปิดไปถูกหน้าหลักที่คนหาเจอพอดี
        target_view_page = page - start_page + 1
        
        return send_file(
            pdf_stream,
            mimetype="application/pdf",
            download_name=f"{model}_page_{page}.pdf",
            as_attachment=False
        )
        
    except Exception as e:
        print(f"❌ Error cropping PDF: {e}")
        return "Error loading PDF snippet", 500


@app.route("/referral", methods=["POST"])
def referral():
    if not sheet:
        return jsonify({"success": False, "error": "Google Sheets offline"}), 500

    data = request.json or {}
    your_name = data.get("your_name", "").strip()
    your_phone = data.get("your_phone", "").strip()
    friend_name = data.get("friend_name", "").strip()
    friend_phone = data.get("friend_phone", "").strip()

    if not (your_name and your_phone and friend_name and friend_phone):
        return jsonify({"success": False, "error": "Required fields are missing"}), 400

    try:
        sheet.append_row([your_name, your_phone, friend_name, friend_phone, data.get("model", ""), data.get("note", "")])
        return jsonify({"success": True})
    except Exception as e:
        print("❌ Google Sheets Error:", e)
        return jsonify({"success": False, "error": "Database error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)