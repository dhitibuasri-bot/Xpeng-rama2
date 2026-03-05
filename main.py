import os
import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
# อนุญาต CORS จากทุกที่เพื่อให้ Frontend บน GitHub Pages เรียกได้
CORS(app, resources={r"/*": {"origins": "*"}})

# Cache สำหรับเก็บข้อความ
manual_cache = {}

def clean_thai_text(text):
    if not text: return ""
    text = re.sub(r'(?<=[\u0e00-\u0e7f])\s+(?=[\u0e00-\u0e7f])', '', text)
    text = text.replace('\n', ' ')
    return re.sub(r'\s+', ' ', text).strip()

def get_manual_path(model):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.join(current_dir, "manuals")
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
                # โหลดเฉพาะข้อความเพื่อประหยัด RAM (ไม่โหลดรูปภาพ)
                with fitz.open(path) as doc:
                    pages_data = []
                    for page_num in range(len(doc)):
                        page = doc.load_page(page_num)
                        text = page.get_text("text") # ดึงเฉพาะ text
                        pages_data.append({
                            "page": page_num + 1,
                            "text": clean_thai_text(text),
                            "model": model
                        })
                    manual_cache[model] = pages_data
                    print(f"✅ Loaded {model}: {len(pages_data)} pages")
            except Exception as e:
                print(f"❌ Error loading {model}: {e}")

# --- สำคัญ: เรียกโหลดข้อมูลที่นี่เพื่อให้ Gunicorn ทำงานได้ ---
preload_manuals()

@app.route('/')
def home():
    return jsonify({"status": "online", "models": list(manual_cache.keys())})

@app.route('/view/<model>')
def view_pdf(model):
    path = get_manual_path(model)
    if not path: return "File not found", 404
    return send_from_directory(os.path.dirname(path), os.path.basename(path))

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    if not data: return jsonify([])
    
    query = data.get('query', '').strip()
    model = data.get('model', 'G6')
    
    if not query: return jsonify([])

    content = manual_cache.get(model)
    if not content:
        return jsonify({"error": f"No data for {model}"}), 404

    search_q = query.replace(" ", "").lower()
    results = []

    for item in content:
        text_for_search = item['text'].replace(" ", "").lower()
        if search_q in text_for_search:
            original_text = item['text']
            found_idx = original_text.lower().find(query.lower())
            
            start_pos = max(0, found_idx - 60) if found_idx != -1 else 0
            snippet = original_text[start_pos:start_pos+300]
            
            results.append({
                "page": item["page"],
                "text": f"...{snippet.strip()}...",
                "model": item["model"]
            })

    return jsonify(results[:15]) # จำกัดจำนวนผลลัพธ์เพื่อความเร็ว

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)