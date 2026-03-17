import os
import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io

app = Flask(__name__)
CORS(app)

# --- Memory Cache ---
pdf_content_cache = {"G6": [], "X9": []}

def clean_thai_text(text):
    if not text: return ""
    text = re.sub(r'(?<=[\u0e00-\u0e7f])\s+(?=[\u0e00-\u0e7f])', '', text)
    text = text.replace('\n', ' ')
    return re.sub(r'\s+', ' ', text).strip()

def find_pdf_file(model_name):
    """ ค้นหาไฟล์ PDF ในโฟลเดอร์ manuals แบบไม่สนใจตัวพิมพ์เล็ก-ใหญ่ """
    manuals_dir = os.path.join(os.getcwd(), "manuals")
    if not os.path.exists(manuals_dir):
        return None
    
    # ดึงรายชื่อไฟล์ทั้งหมดในโฟลเดอร์ manuals
    files = os.listdir(manuals_dir)
    for f in files:
        # ถ้าไฟล์ลงท้ายด้วย .pdf และมีชื่อ model (เช่น g6 หรือ G6) อยู่ในชื่อไฟล์
        if f.lower().endswith('.pdf') and model_name.lower() in f.lower():
            return os.path.join(manuals_dir, f)
    return None

def load_all_manuals():
    print("--- 🔍 STARTING AUTO-SCAN PDF ---")
    for model in ["G6", "X9"]:
        path = find_pdf_file(model)
        if path:
            try:
                print(f"📖 Found file for {model}: {path}")
                with fitz.open(path) as doc:
                    content = []
                    for page in doc:
                        content.append(clean_thai_text(page.get_text("text")))
                    pdf_content_cache[model] = content
                print(f"✅ LOADED: {model} ({len(content)} pages)")
            except Exception as e:
                print(f"❌ ERROR reading {model}: {e}")
        else:
            print(f"⚠️ NOT FOUND: No PDF file containing '{model}' in manuals folder")

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "cache_status": {
            "G6": f"{len(pdf_content_cache['G6'])} pages",
            "X9": f"{len(pdf_content_cache['X9'])} pages"
        },
        "debug_info": {
            "files_in_manuals": os.listdir("manuals") if os.path.exists("manuals") else "folder_not_found"
        }
    })

@app.route('/view/<model>')
def view_pdf(model):
    path = find_pdf_file(model)
    target_page = request.args.get('page', default=1, type=int)
    if not path: return "File not found", 404
    try:
        with fitz.open(path) as doc:
            current_idx = target_page - 1
            start = max(0, current_idx - 2)
            end = min(len(doc) - 1, current_idx + 2)
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=start, to_page=end)
            pdf_bytes = new_doc.write()
            new_doc.close()
            output = io.BytesIO(pdf_bytes)
            output.seek(0)
            return send_file(output, mimetype='application/pdf')
    except Exception as e:
        return str(e), 500

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    model = data.get('model', 'G6').upper()
    if not query or model not in pdf_content_cache or not pdf_content_cache[model]:
        return jsonify([])
    
    results = []
    search_q = query.replace(" ", "").lower()
    for idx, text in enumerate(pdf_content_cache[model]):
        if search_q in text.replace(" ", "").lower():
            f_idx = text.lower().find(query.lower())
            start_snip = max(0, f_idx - 60)
            results.append({
                "page": idx + 1,
                "text": f"...{text[start_snip:start_snip+250].strip()}...",
                "model": model
            })
        if len(results) >= 15: break
    return jsonify(results)

if __name__ == '__main__':
    load_all_manuals()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)