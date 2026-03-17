import os
import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io

app = Flask(__name__)
CORS(app)

# --- Global Cache ---
pdf_content_cache = {"G6": [], "X9": []}

def clean_thai_text(text):
    if not text: return ""
    # แก้ปัญหาช่องว่างในภาษาไทย
    text = re.sub(r'(?<=[\u0e00-\u0e7f])\s+(?=[\u0e00-\u0e7f])', '', text)
    text = text.replace('\n', ' ')
    return re.sub(r'\s+', ' ', text).strip()

def find_pdf_path(model):
    """ หา Path ของไฟล์ PDF """
    base_path = os.path.join(os.getcwd(), "manuals")
    filename = f"{model.upper()}.pdf"
    full_path = os.path.join(base_path, filename)
    return full_path if os.path.exists(full_path) else None

def ensure_loaded(model):
    """ ตรวจสอบว่าโหลดข้อมูลหรือยัง ถ้ายังให้โหลดทันที """
    model = model.upper()
    if not pdf_content_cache.get(model):
        path = find_pdf_path(model)
        if path:
            try:
                print(f"🔄 Loading {model} on demand...")
                with fitz.open(path) as doc:
                    content = [clean_thai_text(page.get_text()) for page in doc]
                    pdf_content_cache[model] = content
                print(f"✅ Loaded {model}: {len(content)} pages")
            except Exception as e:
                print(f"❌ Error loading {model}: {e}")

@app.route('/')
def home():
    # เช็คทั้ง G6 และ X9
    ensure_loaded("G6")
    ensure_loaded("X9")
    
    manuals_dir = os.path.join(os.getcwd(), "manuals")
    files = os.listdir(manuals_dir) if os.path.exists(manuals_dir) else []
    
    return jsonify({
        "status": "online",
        "cache_status": {m: f"{len(pdf_content_cache[m])} pages" for m in pdf_content_cache},
        "files_found": files
    })

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    model = data.get('model', 'G6').upper()
    
    # บังคับโหลดก่อนค้นหา
    ensure_loaded(model)
    
    if not query or not pdf_content_cache.get(model):
        return jsonify([])

    results = []
    search_q = query.replace(" ", "").lower()
    
    for idx, text in enumerate(pdf_content_cache[model]):
        if search_q in text.replace(" ", "").lower():
            # ดึงข้อความรอบๆ คำที่หาเจอ
            start_idx = max(0, text.lower().find(query.lower()) - 50)
            snippet = text[start_idx:start_idx+200]
            results.append({
                "page": idx + 1,
                "text": f"...{snippet.strip()}...",
                "model": model
            })
        if len(results) >= 15: break
            
    return jsonify(results)

@app.route('/view/<model>')
def view_pdf(model):
    path = find_pdf_path(model)
    if not path: return "File not found", 404
    # ส่งไฟล์ PDF ทั้งไฟล์เพื่อให้ Frontend ไปจัดการเลขหน้าเอง
    return send_file(path, mimetype='application/pdf')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)