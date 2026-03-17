import os
import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io
import threading

app = Flask(__name__)
CORS(app)

# --- Global Cache (เก็บข้อมูลใน RAM เพื่อความเร็วสูงสุด) ---
pdf_content_cache = {"G6": [], "X9": []}
load_status = {"G6": "Idle", "X9": "Idle"}

def clean_thai_text(text):
    if not text: return ""
    text = re.sub(r'(?<=[\u0e00-\u0e7f])\s+(?=[\u0e00-\u0e7f])', '', text)
    return text.replace('\n', ' ').strip()

def load_pdf_worker(model):
    """ฟังก์ชันทำงานเบื้องหลังเพื่อโหลดไฟล์เข้าแรม"""
    model = model.upper()
    path = os.path.join(os.getcwd(), "manuals", f"{model}.pdf")
    if os.path.exists(path):
        try:
            load_status[model] = "Loading..."
            print(f"🔄 X-tech: เริ่มโหลด {model} เข้า RAM...")
            with fitz.open(path) as doc:
                content = [clean_thai_text(page.get_text()) for page in doc]
                pdf_content_cache[model] = content
            load_status[model] = "Ready"
            print(f"✅ X-tech: {model} โหลดเสร็จแล้ว! ({len(content)} หน้า)")
        except Exception as e:
            load_status[model] = f"Error: {str(e)}"
    else:
        load_status[model] = "File Not Found"

def start_preloading():
    """สั่งโหลดไฟล์ G6 และ X9 ทันทีแบบไม่ต้องรอ"""
    threading.Thread(target=load_pdf_worker, args=("G6",)).start()
    threading.Thread(target=load_pdf_worker, args=("X9",)).start()

# สั่งเริ่มโหลดทันทีที่รัน Server
start_preloading()

@app.route('/')
def home():
    return jsonify({
        "service": "X-tech Rama 2 Service Support",
        "system_status": load_status,
        "cache_pages": {m: len(pdf_content_cache[m]) for m in pdf_content_cache}
    })

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    model = data.get('model', 'G6').upper()
    
    # ถ้าข้อมูลใน RAM ยังไม่มี ให้ส่งกลับไปก่อนว่าว่าง (ป้องกันค้าง)
    if not pdf_content_cache.get(model):
        return jsonify([])

    results = []
    search_q = query.replace(" ", "").lower()
    
    # ค้นหาจาก RAM (เร็วระดับมิลลิวินาที)
    for idx, text in enumerate(pdf_content_cache[model]):
        if search_q in text.replace(" ", "").lower():
            found_pos = text.lower().find(query.lower())
            start_snip = max(0, found_pos - 60)
            results.append({
                "page": idx + 1,
                "text": f"...{text[start_snip:start_snip+200].strip()}...",
                "model": model
            })
        if len(results) >= 15: break
    return jsonify(results)

@app.route('/view/<model>')
def view_pdf(model):
    path = os.path.join(os.getcwd(), "manuals", f"{model.upper()}.pdf")
    target_page = request.args.get('page', default=1, type=int)
    if not os.path.exists(path): return "File not found", 404
    try:
        with fitz.open(path) as doc:
            current_idx = target_page - 1
            # ส่งแค่ 3 หน้า (ลดภาระเน็ตและ RAM)
            start = max(0, current_idx - 1)
            end = min(len(doc) - 1, current_idx + 1)
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=start, to_page=end)
            pdf_bytes = new_doc.write()
            new_doc.close()
            output = io.BytesIO(pdf_bytes)
            output.seek(0)
            return send_file(output, mimetype='application/pdf')
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)