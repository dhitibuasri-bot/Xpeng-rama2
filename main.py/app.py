import os
import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Cache สำหรับเก็บข้อความจาก PDF เพื่อการค้นหาที่รวดเร็ว
manual_cache = {}

def clean_thai_text(text):
    if not text: return ""
    # เชื่อมสระและพยัญชนะไทยที่มักแยกกันจากการ Extract PDF
    # ใช้ Regex จัดการช่องว่างระหว่างตัวอักษรภาษาไทย
    text = re.sub(r'(?<=[\u0e00-\u0e7f])\s+(?=[\u0e00-\u0e7f])', '', text)
    # เปลี่ยนการขึ้นบรรทัดใหม่เป็นช่องว่างเดียว
    text = text.replace('\n', ' ')
    # ลบช่องว่างที่ซ้ำซ้อน
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_manual_path(model):
    # กำหนด Path ให้ปลอดภัยและรองรับการรันบน Server
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.join(current_dir, "manuals")
    
    # ตรวจสอบชื่อรุ่นให้ปลอดภัย (Whitelist)
    safe_model = "G6" if model.upper() == "G6" else "X9" if model.upper() == "X9" else None
    if not safe_model: return None

    filename = f"{safe_model}.pdf"
    full_path = os.path.join(base_dir, filename)
    return full_path if os.path.exists(full_path) else None

def preload_manuals():
    global manual_cache
    models = ["G6", "X9"]
    for model in models:
        path = get_manual_path(model)
        if path:
            try:
                doc = fitz.open(path)
                pages_data = []
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    text = page.get_text()
                    pages_data.append({
                        "page": page_num + 1,
                        "text": clean_thai_text(text),
                        "model": model
                    })
                manual_cache[model] = pages_data
                print(f"✅ โหลด {model} สำเร็จ! ({len(pages_data)} หน้า)")
                doc.close()
            except Exception as e:
                print(f"❌ ไม่สามารถอ่านไฟล์ {model}: {e}")

@app.route('/view/<model>')
def view_pdf(model):
    path = get_manual_path(model)
    if not path:
        return "ไม่สามารถยืนยันไฟล์ที่ต้องการได้", 404
    return send_from_directory(os.path.dirname(path), os.path.basename(path))

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    query = data.get('query', '').strip()
    model = data.get('model', 'G6')
    
    if not query: 
        return jsonify([])

    content = manual_cache.get(model)
    if not content:
        # [ยังไม่ยืนยัน] กรณีไม่มีข้อมูลใน Cache
        return jsonify({"error": f"ไม่พบข้อมูลคู่มือรุ่น {model} ในระบบ"}), 404

    # เตรียมคำค้นหา (ลบช่องว่างเพื่อความแม่นยำในภาษาไทย)
    search_q = query.replace(" ", "").lower()
    results = []

    for item in content:
        # ตรวจสอบโดยลบช่องว่างใน Text ที่จะหาด้วย
        text_for_search = item['text'].replace(" ", "").lower()
        
        if search_q in text_for_search:
            original_text = item['text']
            
            # ค้นหาตำแหน่งเพื่อตัด Snippet (แสดงบริบทคำ)
            # พยายามหาตำแหน่งแบบที่มีช่องว่างก่อน
            found_idx = original_text.lower().find(query.lower())
            
            # ถ้าหาไม่เจอ (เพราะช่องว่างต่างกัน) ให้เริ่มที่ต้นหน้าหรือจุดที่ใกล้เคียง
            start_pos = max(0, found_idx - 60) if found_idx != -1 else 0
            end_pos = min(len(original_text), start_pos + 300)
            
            snippet = original_text[start_pos:end_pos]
            
            results.append({
                "page": item["page"],
                "text": f"...{snippet.strip()}...",
                "model": item["model"]
            })

    # ส่งผลลัพธ์สูงสุด 20 รายการเพื่อความรวดเร็ว
    return jsonify(results[:20])

if __name__ == '__main__':
    preload_manuals()
    # บน Render ต้องใช้ port จาก environment variable หรือ default เป็น 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)