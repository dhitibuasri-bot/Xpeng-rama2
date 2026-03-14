import os
import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
# อนุญาตให้ Frontend จาก GitHub Pages เรียกใช้งานได้
CORS(app, resources={r"/*": {"origins": "*"}})

def clean_thai_text(text):
    if not text: return ""
    # แก้ไขสระ/พยัญชนะไทยที่มักแยกห่างกันจากการ Extract PDF
    text = re.sub(r'(?<=[\u0e00-\u0e7f])\s+(?=[\u0e00-\u0e7f])', '', text)
    text = text.replace('\n', ' ')
    return re.sub(r'\s+', ' ', text).strip()

def get_manual_path(model):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.join(current_dir, "manuals")
    
    # ตรวจสอบชื่อรุ่นให้ตรงกับไฟล์ (Case-sensitive สำหรับ Linux)
    safe_model = "G6" if model.upper() == "G6" else "X9" if model.upper() == "X9" else None
    if not safe_model: return None

    filename = f"{safe_model}.pdf"
    full_path = os.path.join(base_dir, filename)
    return full_path if os.path.exists(full_path) else None

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "XPENG Assistant API by X-Tech RAMA 2"})

@app.route('/view/<model>')
def view_pdf(model):
    path = get_manual_path(model)
    if not path:
        return "ไม่สามารถยืนยันไฟล์ที่ต้องการได้", 404
    
    # ส่ง mimetype เพื่อให้ Browser เข้าใจว่าเป็น PDF และยอมรับ Fragment #page
    return send_from_directory(
        os.path.dirname(path), 
        os.path.basename(path),
        mimetype='application/pdf'
    )

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    if not data: return jsonify([])
    
    query = data.get('query', '').strip()
    model = data.get('model', 'G6').upper()
    
    if not query: return jsonify([])

    path = get_manual_path(model)
    if not path:
        return jsonify({"error": f"ไม่พบข้อมูลคู่มือรุ่น {model}"}), 404

    results = []
    # ลบช่องว่างในคำค้นหาเพื่อให้แมตช์กับข้อความภาษาไทยได้ง่ายขึ้น
    search_q = query.replace(" ", "").lower()

    try:
        # เปิดไฟล์แบบ On-demand (อ่านเมื่อค้นหาเท่านั้น) เพื่อประหยัด RAM
        with fitz.open(path) as doc:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text("text")
                clean_text = clean_thai_text(text)
                
                # ตรวจสอบโดยลบช่องว่างในเนื้อหาที่ค้นหาด้วย
                if search_q in clean_text.replace(" ", "").lower():
                    found_idx = clean_text.lower().find(query.lower())
                    start_pos = max(0, found_idx - 60)
                    snippet = clean_text[start_pos:start_pos + 300]
                    
                    results.append({
                        "page": page_num + 1,
                        "text": f"...{snippet.strip()}...",
                        "model": model
                    })
                
                # จำกัดที่ 15 รายการเพื่อความเร็ว
                if len(results) >= 15: break
                    
        return jsonify(results)
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "ระบบขัดข้องในการอ่านไฟล์"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)