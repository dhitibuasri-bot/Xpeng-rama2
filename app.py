from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

import fitz
import os
import json
import gspread
import re
import io
from datetime import datetime  # 🟢 ข้อ 5: สำหรับบันทึกวันเวลา
from pythainlp.tokenize import word_tokenize  # 🟢 ข้อ 1: คลังตัดคำภาษาไทยสำหรับทำ Fuzzy Search

from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__, static_folder='static', static_url_path='/static')
# ล็อกให้เฉพาะเว็บของน้าดิษเท่านั้นที่ดึงข้อมูลได้
CORS(app, origins=["https://dhitibuasri-bot.github.io"])

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

# รายชื่อไฟล์คู่มือเทคนิค
PDFS = {
    "G6": "manuals/G6.pdf",
    "X9_2026": "manuals/X9_2026.pdf",
    "SCREEN": "manuals/frequent_settings.pdf"
}

# 🟢 ข้อ 1: คลังคำศัพท์เทคนิคภาษาไทย 50 คำที่ใช้งานบ่อยหน้างาน (อัปเดตชุดใหญ่)
SYNONYMS = {
    # 🚗 หมวดระบบขับเคลื่อน / แบตเตอรี่ / การชาร์จ
    "เบรค": "เบรก",
    "แอร์": "ระบบปรับอากาศ",
    "ชาร์จ": "ประจุไฟ",
    "แบต": "แบตเตอรี่",
    "แบตเตอรรี่": "แบตเตอรี่",
    "เต้ารับ": "พอร์ตชาร์จ",
    "ตู้ชาร์จ": "สถานีชาร์จ",
    "ไฟกระแสสลับ": "ac",
    "ไฟกระแสตรง": "dc",
    "โหมดประหยัด": "eco",
    "ขับคนเดียว": "โหมดขับเคลื่อนด้วยมอเตอร์เดี่ยว",
    "วันเพดดอล": "one-pedal",
    "สลับแบต": "v2l",
    
    # 📱 หมวดหน้าจอ / ระบบความบันเทิง / การเชื่อมต่อ
    "หน้าจอ": "จอแสดงผล",
    "จอกลาง": "จอควบคุมส่วนกลาง",
    "จอหลัง": "จอแสดงผลอเนกประสงค์ด้านหลัง",
    "ไวไฟ": "wifi",
    "บลูทูธ": "bluetooth",
    "บลูทูช": "bluetooth",
    "ต่อมือถือ": "การเชื่อมต่อโทรศัพท์",
    "เน็ต": "อินเทอร์เน็ต",
    "จอนำทาง": "ระบบนำทาง",
    "แผนที่": "ระบบนำทาง導航",
    "คีย์": "กุญแจ",
    "กุญแจมือถือ": "กุญแจดิจิทัล",
    "แอป": "แอปพลิเคชัน",
    
    # 💺 หมวดห้องโดยสาร / เบาะนั่ง / ความสะดวกสบาย
    "เบาะ": "เบาะนั่ง",
    "เบาะนวด": "ระบบนวดเบาะนั่ง",
    "เบาะร้อน": "ระบบทำความร้อนเบาะนั่ง",
    "เบาะเย็น": "ระบบระบายอากาศเบาะนั่ง",
    "พวงมาลัย": "พวงมาลัยมัลติฟังก์ชัน",
    "ซันรูฟ": "หลังคากระจกพาโนรามา",
    "ที่ชาร์จไร้สาย": "การชาร์จแบบไร้สายของโทรศัพท์",
    "ตู้เย็น": "กล่องทำความเย็นอัจฉริยะ",
    "แผ่นกั้น": "แผ่นปิดห้องสัมภาระท้าย",
    
    # 🛡️ หมวดระบบความปลอดภัย / ADAS / กล้อง / เซนเซอร์
    "กล้อง": "กล้องมองภาพรอบทิศทาง",
    "กล้อง360": "ภาพพาโนรามา 360",
    "ถุงลม": "ถุงลมนิรภัย",
    "เรดาร์": "เรดาร์คลื่นมิลลิเมตร",
    "เซนเซอร์": "เซนเซอร์อัลตราโซนิก",
    "ขับอัตโนมัติ": "xngp",
    "ประคองเลน": "ระบบช่วยควบคุมรถให้อยู่ในเลน",
    "เตือนชน": "ระบบช่วยเตือนการชน",
    "ช่วยจอด": "ระบบช่วยจอดรถอัจฉริยะ",
    "ครูสคอนโทรล": "ระบบควบคุมความเร็วอัตโนมัติ",
    
    # 🛠️ หมวดตัวถัง / ไฟแสงสว่าง / และระบบกลไกรอบรถ
    "ไฟหน้า": "โคมไฟหน้า",
    "ไฟเลี้ยว": "สัญญาณไฟเลี้ยว",
    "ไฟสูง": "ไฟสูงอัจฉริยะ",
    "ยาง": "ความดันลมยาง",
    "ลมยาง": "ระบบตรวจสอบความดันลมยาง(tpms)",
    "ประตูท้าย": "ประตูท้ายไฟฟ้า",
    "ฝากระโปรง": "ฝากระโปรงหน้า",
    "เด้ง": "มือจับประตูมือจับ",
    "ที่ปัดน้ำฝน": "ก้านปัดน้ำฝน",
    "กระจกมองข้าง": "กระจกมองหลังภายนอก"
}

pdf_data = []
CACHE_FILE = "manuals/pdf_text_cache.json"  # 🟢 ข้อ 2: ไฟล์เก็บข้อมูลแคชข้อความ

def load_pdf_manuals():
    """🟢 ข้อ 2: ระบบตรวจเช็กข้อความจากแคช JSON สตาร์ทไว ไม่ค้าง ไม่กิน RAM บน Render"""
    global pdf_data
    if pdf_data: 
        return

    # ถ้ามีไฟล์แคช JSON อยู่แล้ว ดึงมาใช้ทันทีประหยัดเวลา
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                pdf_data = json.load(f)
            return
        except:
            pass

    # ถ้ายังไม่มีไฟล์แคช ค่อยแกะจาก PDF และเซฟเก็บไว้เป็น JSON
    for model, path in PDFS.items():
        if model == "SCREEN" or not os.path.exists(path): continue
        try:
            doc = fitz.open(path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text("text", sort=True)
                # จัดการวรรณยุกต์ภาษาไทยจมลอย
                text = re.sub(r'([ก-๙])\s+([่้๊๋ัิีึืุู็์ำ])', r'\1\2', text)
                pdf_data.append({"model": model, "page": page_num + 1, "text": text})
        except Exception as e:
            print(f"Error parsing {model}: {e}")
            
    # บันทึกข้อความลงแคช JSON
    if pdf_data:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(pdf_data, f, ensure_ascii=False, indent=2)

# 🟢 ข้อ 2: โหลดข้อมูลเตรียมพร้อมตั้งแต่เปิด Server
with app.app_context():
    load_pdf_manuals()

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

        # 🟢 ข้อ 1: แปลงคำค้นหาจากระบบแปลงคำเหมือน (Synonym)
        for wrong, right in SYNONYMS.items():
            query = query.replace(wrong, right)
            
        # ใช้ pythainlp ตัดคำเพื่อทำ Fuzzy Search แยกคำสั้น-ยาว
        query_words = word_tokenize(query.lower(), engine="newmm")
        query_words = [w for w in query_words if w.strip() and len(w) > 1]

        results = []
        for item in pdf_data:
            if item["model"] != model: continue
            clean_text = item["text"].lower()

            # เช็กความแม่นยำ (คำค้นหาตรงกับข้อความในคู่มือหน้าดังกล่าวเกิน 80% หรือไม่)
            matches = sum(1 for word in query_words if word in clean_text)
            if len(query_words) > 0 and (matches / len(query_words)) >= 0.8:
                results.append({
                    "model": item["model"],
                    "page": item["page"],
                    "text": item["text"],
                    "score": matches
                })
                
        # เรียงหน้าคู่มือที่มีความเกี่ยวข้องสูงสุดขึ้นก่อน
        results = sorted(results, key=lambda x: x["score"], reverse=True)
        return jsonify(results[:10])
    except Exception as e:
        print(f"Search error: {e}")
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
        # 🟢 ข้อ 3: ระบบตรวจสอบความถูกต้องของเบอร์โทรศัพท์มือถือ (ต้องขึ้นด้วย 0 และยาว 9-10 หลัก)
        friend_phone = data.get("friend_phone", "").strip()
        if not re.match(r'^0[0-9]{8,9}$', friend_phone):
            return jsonify({"success": False, "message": "รูปแบบเบอร์โทรศัพท์ผู้ถูกแนะนำไม่ถูกต้อง"}), 400

        # 🟢 ข้อ 5: ดึงเวลาปัจจุบันรูปแบบประเทศไทย (Timestamp)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # บันทึกแถวข้อมูลลง Google Sheet โดยเอาวันเวลานำหน้าสุด
        sheet.append_row([
            timestamp, 
            data.get("your_name"), 
            data.get("your_phone"), 
            data.get("friend_name"), 
            friend_phone, 
            data.get("model"), 
            data.get("note")
        ])
        return jsonify({"success": True})
    except Exception as e:
        print(f"Referral entry error: {e}")
        return jsonify({"success": False}), 500

main = app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)