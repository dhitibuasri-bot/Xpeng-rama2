import os
import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_file, make_response
from flask_cors import CORS
import io

app = Flask(__name__)
CORS(app)

def get_manual_path(model):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.join(current_dir, "manuals")
    safe_model = "G6" if model.upper() == "G6" else "X9" if model.upper() == "X9" else None
    if not safe_model: return None
    filename = f"{safe_model}.pdf"
    full_path = os.path.join(base_dir, filename)
    return full_path if os.path.exists(full_path) else None

@app.route('/view/<model>')
def view_pdf(model):
    path = get_manual_path(model)
    page_num = request.args.get('page', default=1, type=int)
    
    if not path: return "ไม่พบไฟล์", 404

    try:
        # เปิดไฟล์ PDF และดึงเฉพาะหน้าที่ต้องการ
        with fitz.open(path) as doc:
            # page_num - 1 เพราะ PDF เริ่มนับจาก 0
            actual_page = max(0, min(page_num - 1, len(doc) - 1))
            
            # สร้าง PDF ใหม่ที่มีแค่หน้าเดียว
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=actual_page, to_page=actual_page)
            
            # แปลงเป็น Bytes เพื่อส่งออก
            pdf_bytes = new_doc.write()
            new_doc.close()

            # ส่งไฟล์กลับไป (เป็นไฟล์หน้าเดียว)
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
    # ... (โค้ดค้นหาเดิมของคุณ ใช้ได้เลยไม่ต้องแก้) ...
    data = request.get_json()
    query = data.get('query', '').strip()
    model = data.get('model', 'G6').upper()
    path = get_manual_path(model)
    if not path: return jsonify([])
    
    results = []
    search_q = query.replace(" ", "").lower()
    try:
        with fitz.open(path) as doc:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text("text")
                if search_q in text.replace(" ", "").lower():
                    results.append({
                        "page": page_num + 1,
                        "text": text[:300].strip(),
                        "model": model
                    })
                if len(results) >= 15: break
        return jsonify(results)
    except: return jsonify([])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)