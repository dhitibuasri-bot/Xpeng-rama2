import os
import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_file, make_response
from flask_cors import CORS
import io

app = Flask(__name__)
CORS(app)

def clean_thai_text(text):
    if not text: return ""
    # 1. กำจัดช่องว่างระหว่างตัวอักษรไทย (แก้ปัญหา ก า ร ท า -> การทำ)
    text = re.sub(r'(?<=[\u0e00-\u0e7f])\s+(?=[\u0e00-\u0e7f])', '', text)
    # 2. กำจัดการขึ้นบรรทัดใหม่
    text = text.replace('\n', ' ')
    # 3. ยุบช่องว่างที่ซ้ำซ้อน
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_manual_path(model):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.join(current_dir, "manuals")
    safe_model = "G6" if model.upper() == "G6" else "X9" if model.upper() == "X9" else None
    if not safe_model: return None
    filename = f"{safe_model}.pdf"
    full_path = os.path.join(base_dir, filename)
    return full_path if os.path.exists(full_path) else None

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "XPENG Assistant API - Thai Fixed & Page Splitter"})

@app.route('/view/<model>')
def view_pdf(model):
    path = get_manual_path(model)
    page_num = request.args.get('page', default=1, type=int)
    if not path: return "File not found", 404

    try:
        with fitz.open(path) as doc:
            # ปรับเลขหน้า (เริ่มจาก 0)
            actual_page = max(0, min(page_num - 1, len(doc) - 1))
            
            # สร้าง PDF ใหม่ที่มีเฉพาะหน้านั้น
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=actual_page, to_page=actual_page)
            pdf_bytes = new_doc.write()
            new_doc.close()

            output = io.BytesIO(pdf_bytes)
            return send_file(
                output,
                mimetype='application/pdf',
                as_attachment=False,
                download_name=f"{model}_page_{page_num}.pdf"
            )
    except Exception as e:
        return str(e), 500

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    if not data: return jsonify([])
    
    query = data.get('query', '').strip()
    model = data.get('model', 'G6').upper()
    if not query: return jsonify([])

    path = get_manual_path(model)
    if not path: return jsonify([])

    results = []
    # ลบช่องว่างในคำค้นหาเพื่อให้หาเจอแม้อักษรใน PDF จะเว้นวรรค
    search_q = query.replace(" ", "").lower()

    try:
        with fitz.open(path) as doc:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                # ใช้การดึงแบบ blocks เพื่อให้ได้ลำดับคำที่ดีขึ้น
                blocks = page.get_text("blocks")
                page_content = " ".join([b[4] for b in blocks])
                
                clean_text = clean_thai_text(page_content)
                
                # ตรวจสอบโดยเทียบแบบไม่สนช่องว่าง
                if search_q in clean_text.replace(" ", "").lower():
                    # หาตำแหน่งเพื่อทำ Snippet
                    found_idx = clean_text.lower().find(query.lower())
                    if found_idx == -1: # ถ้าหาแบบเป๊ะๆ ไม่เจอ ให้หาแบบไร้ช่องว่าง
                         found_idx = clean_text.replace(" ","").lower().find(search_q)
                    
                    start = max(0, found_idx - 60)
                    snippet = clean_text[start:start+250]
                    
                    results.append({
                        "page": page_num + 1,
                        "text": f"...{snippet.strip()}...",
                        "model": model
                    })
                if len(results) >= 15: break
        return jsonify(results)
    except:
        return jsonify([])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)