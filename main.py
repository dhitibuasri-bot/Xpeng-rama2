import os
import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io

app = Flask(__name__)
CORS(app)

# --- Config & Cache ---
pdf_content_cache = {"G6": [], "X9": []}

def clean_thai_text(text):
    if not text: return ""
    text = re.sub(r'(?<=[\u0e00-\u0e7f])\s+(?=[\u0e00-\u0e7f])', '', text)
    text = text.replace('\n', ' ')
    return re.sub(r'\s+', ' ', text).strip()

def find_pdf_file(model_name):
    """ ค้นหาไฟล์ PDF ในโฟลเดอร์ manuals แบบยืดหยุ่น """
    manuals_dir = os.path.join(os.getcwd(), "manuals")
    if not os.path.exists(manuals_dir):
        return None
    try:
        files = os.listdir(manuals_dir)
        for f in files:
            if f.lower().endswith('.pdf') and model_name.lower() in f.lower():
                return os.path.join(manuals_dir, f)
    except:
        pass
    return None

def load_all_manuals():
    """ โหลด PDF เข้า Memory """
    for model in ["G6", "X9"]:
        path = find_pdf_file(model)
        if path:
            try:
                with fitz.open(path) as doc:
                    content = [clean_thai_text(page.get_text()) for page in doc]
                    pdf_content_cache[model] = content
                print(f"✅ SUCCESS: {model} loaded {len(content)} pages.")
            except Exception as e:
                print(f"❌ ERROR: {model} failed: {e}")
        else:
            print(f"⚠️ NOT FOUND: {model}.pdf")

# บังคับโหลดทันทีที่ Start
load_all_manuals()

@app.route('/')
def home():
    manuals_dir = os.path.join(os.getcwd(), "manuals")
    files_found = os.listdir(manuals_dir) if os.path.exists(manuals_dir) else "folder_not_found"
    return jsonify({
        "status": "online",
        "cache": {m: f"{len(pdf_content_cache[m])} pages" for m in pdf_content_cache},
        "manuals_folder_files": files_found
    })

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    model = data.get('model', 'G6').upper()
    if not query or model not in pdf_content_cache: return jsonify([])
    
    results = []
    search_q = query.replace(" ", "").lower()
    for idx, text in enumerate(pdf_content_cache.get(model, [])):
        if search_q in text.replace(" ", "").lower():
            results.append({
                "page": idx + 1,
                "text": text[:200] + "...",
                "model": model
            })
        if len(results) >= 15: break
    return jsonify(results)

@app.route('/view/<model>')
def view_pdf(model):
    path = find_pdf_file(model)
    if not path: return "File not found", 404
    return send_file(path, mimetype='application/pdf')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)