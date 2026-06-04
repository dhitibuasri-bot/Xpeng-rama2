from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

import fitz
import os
import json
import gspread
import re

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

# ตรวจสอบ Environment Variable เพื่อป้องกัน Error ตอนแอปพลิเคชันเริ่มต้นทำงาน
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
    """ฟังก์ชันสำหรับโหลดและจัดการสระลอยจากคู่มือรถยนต์เฉพาะรุ่นที่จำเป็น"""
    global pdf_data
    if pdf_data:  # ถ้าเคยโหลดเข้าระบบเรียบร้อยแล้ว ให้ข้ามได้เลย
        return

    print("\n🔥 Loading PDF manuals into server memory...\n")
    
    for model, path in PDFS.items():
        # 📺 ทางลัดสำหรับ SCREEN ถูกจัดการที่ฝั่งหน้าบ้านแบบเมนูด่วน 100% แล้ว
        # จึงสั่งข้ามการโหลดที่ฝั่งเซิร์ฟเวอร์ เพื่อประหยัด CPU, Memory และป้องกันการเกิด Internal Server Error
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
                
                # ดึงข้อความแบบเรียงลำดับเนื้อหาตามโครงสร้างหน้า
                text = page.get_text("text", sort=True)

                # แก้ปัญหาสระลอย / วรรณยุกต์ลอยจากการแปลงไฟล์ภาษาไทยในระบบ PDF
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
    """เส้นทางหลักสำหรับเปิดหน้าแรกของแอปพลิเคชัน"""
    return send_file("index.html")


@app.route("/search", methods=["POST"])
def search():
    """ระบบ API สำหรับค้นหาข้อมูลแบบตัดคำรอบบริบทอัจฉริยะ (Context-Aware Snippet)"""
    try:
        # เรียกฟังก์ชันโหลด PDF เฉพาะเมื่อจำเป็นป้องกัน Startup Time ล่าช้า
        load_pdf_manuals()

        data = request.json or {}
        query = data.get("query", "").strip()
        model = data.get("model", "")

        if not model:
            return jsonify([])

        # หากเป็นรุ่น SCREEN จะไม่มีข้อความใน memory ให้ส่งกลับเป็นลิสต์ว่างทันที ป้องกันแอปพลิเคชันแครช
        if model == "SCREEN":
            return jsonify([])

        if not query:
            return jsonify([])

        results = []
        # ทำความสะอาดคำค้นหาโดยการแปลงเป็นพิมพ์เล็กและตัดช่องว่างส่วนเกินออกเพื่อเพิ่มโอกาสในการค้นพบ
        clean_query = re.sub(r'\s+', '', query.lower())

        for item in pdf_data:
            if item["model"] != model:
                continue

            # ทำความสะอาดเนื้อหาต้นฉบับก่อนทำตามกระบวนการ Matching
            clean_text = re.sub(r'\s+', '', item["text"].lower())

            if clean_query in clean_text:
                original_text = item["text"]
                match_idx = original_text.lower().find(query.lower())
                
                if match_idx != -1:
                    # ปรับแต่ง Snippet ตัดข้อความส่วนหน้า 200 ตัวอักษร และส่วนท้ายคำค้นหา 600 ตัวอักษร เพื่อความเข้าใจบริบทข้อมูล
                    start_idx = max(0, match_idx - 200)
                    end_idx = min(len(original_text), match_idx + 600)
                    snippet = original_text[start_idx:end_idx]
                    if start_idx > 0: 
                        snippet = "..." + snippet
                    if end_idx < len(original_text): 
                        snippet = snippet + "..."
                else:
                    # ระบบ Fallback กรณีคำค้นหาติดฟอร์แมตช่องว่างแปลกๆ ในตัวเล่มให้ตัดข้อความเริ่มต้นหน้า
                    snippet = original_text[:800] + "..."

                results.append({
                    "model": item["model"],
                    "page": item["page"],
                    "text": snippet
                })

        return jsonify(results[:10])

    except Exception as e:
        print("❌ Search API System Error:", e)
        return jsonify({"success": False, "error": "Internal Server Error", "details": str(e)}), 500


@app.route("/view/<model>")
def view_pdf(model):
    """เส้นทางส่งไฟล์ PDF ไปเปิดอ่านบนเบราว์เซอร์ต้นทาง"""
    pdf_path = PDFS.get(model)
    if not pdf_path or not os.path.exists(pdf_path):
        return "PDF Manual Not Found", 404

    return send_file(
        pdf_path,
        mimetype="application/pdf"
    )


@app.route("/referral", methods=["POST"])
def referral():
    """ระบบรับข้อมูลแนะนำเพื่อนเพื่อเขียนบันทึกลงฐานข้อมูล Google Sheets"""
    if not sheet:
        return jsonify({"success": False, "error": "Google Sheets database connection is offline"}), 500

    data = request.json or {}
    
    # ดำเนินการ Data Validation ตรวจเช็คข้อมูลสำคัญฝั่งเซิร์ฟเวอร์เพื่อความถูกต้องขั้นสูง
    your_name = data.get("your_name", "").strip()
    your_phone = data.get("your_phone", "").strip()
    friend_name = data.get("friend_name", "").strip()
    friend_phone = data.get("friend_phone", "").strip()

    if not (your_name and your_phone and friend_name and friend_phone):
        return jsonify({
            "success": False,
            "error": "Data Validation Failed: Required fields are missing"
        }), 400

    try:
        sheet.append_row([
            your_name,
            your_phone,
            friend_name,
            friend_phone,
            data.get("model", ""),
            data.get("note", "")
        ])
        return jsonify({"success": True})

    except Exception as e:
        print("❌ Google Sheets Row Append Error:", e)
        return jsonify({
            "success": False,
            "error": "Failed to write data to database",
            "details": str(e)
        }), 500

# =========================
# APPLICATION LAUNCH
# =========================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )