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

def get_manual_path(model):
    """ฟังก์ชันหา Path แบบยืดหยุ่น"""
    model_upper = model.upper()
    filename = f"{model_upper}.pdf"
    
    # ลองหา 3 ตำแหน่งที่อาจเป็นไปได้
    possible_paths = [
        os.path.join(os.getcwd(), "manuals", filename),           # /opt/render/project/src/manuals/G6.pdf
        os.path.join(os.path.dirname(__file__), "manuals", filename), # path เดียวกับไฟล์รัน
        os.path.abspath(f"manuals/{filename}")                    # path ตรงๆ
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

def load_all_manuals():
    print("--- 🔍 STARTING FILE SCAN ---")
    # ลอง Print รายชื่อไฟล์ใน Root มาดูผ่าน Log เผื่อหาไม่เจออีก
    try:
        print(f"Current Directory: {os.getcwd()}")
        print(f"Files in Current Dir: {os.listdir(os.getcwd())}")
        if os.path.exists("manuals"):
            print(f"Files in 'manuals' folder: {os.listdir('manuals')}")
    except Exception as e:
        print(f"Log Error: {e}")

    for model in ["G6", "X9"]:
        path = get_manual_path(model)
        if path:
            try:
                with fitz.open(path) as doc:
                    content = []
                    for page in doc:
                        content.append(clean_thai_text(page.get_text("text")))
                    pdf_content_cache[model] = content
                print(f"✅ LOADED: {model} ({len(content)} pages)")
            except Exception as e:
                print(f"❌ ERROR reading {model}: {e}")
        else:
            print(f"⚠️ NOT FOUND: {model}.pdf")

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "cache_status": {
            "G6": f"{len(pdf_content_cache['G6'])} pages",
            "X9": f"{len(pdf_content_cache['X9'])} pages"
        },
        "debug_info": {
            "current_dir": os.getcwd(),
            "has_manuals_folder": os.path.exists("manuals")
        }
    })

@app.route('/view/<model>')
def view_pdf(model):
    path = get_manual_path(model)
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
    if not query or model not in pdf_content_cache: return jsonify([])
    
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