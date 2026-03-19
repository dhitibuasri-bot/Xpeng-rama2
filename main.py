import os
import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io
import threading

app = Flask(__name__)
CORS(app)

# --- Global Cache ---
pdf_content_cache = {"G6": [], "X9": [], "SCREEN": []}
load_status = {"G6": "Idle", "X9": "Idle", "SCREEN": "Idle"}
debug_paths = {} # เก็บ Path ที่ระบบพยายามหาเพื่อแสดงบนหน้าเว็บ

def clean_thai_text(text):
    if not text: return ""
    text = re.sub(r'(?<=[\u0e00-\u0e7f])\s+(?=[\u0e00-\u0e7f])', '', text)
    return text.replace('\n', ' ').strip()

def find_pdf_path(filename):
    """ฟังก์ชันช่วยหา Path ของไฟล์ เผื่อว่าไม่ได้อยู่ใน manuals/"""
    paths_to_try = [
        os.path.join(os.getcwd(), "manuals", filename),
        os.path.join(os.getcwd(), filename)
    ]
    for p in paths_to_try:
        if os.path.exists(p):
            return p
    return paths_to_try[0] # คืนค่า path แรกถ้าหาไม่เจอเลย

def load_pdf_worker(model, filename):
    model = model.upper()
    path = find_pdf_path(filename)
    debug_paths[model] = path
    
    print(f"🔍 System checking path for {model}: {path}")
    
    if os.path.exists(path):
        try:
            load_status[model] = "Loading..."
            with fitz.open(path) as doc:
                content = [clean_thai_text(page.get_text()) for page in doc]
                pdf_content_cache[model] = content
            load_status[model] = "Ready"
            print(f"✅ X-tech: {model} loaded ({len(content)} pages)")
        except Exception as e:
            load_status[model] = f"Error: {str(e)}"
            print(f"❌ Error loading {model}: {str(e)}")
    else:
        load_status[model] = f"File Not Found at {path}"
        print(f"⚠️ File Not Found: {path}")

def start_preloading():
    configs = [
        ("G6", "G6.pdf"),
        ("X9", "X9.pdf"),
        ("SCREEN", "การใช้งานหน้าจอ.pdf")
    ]
    for model, fname in configs:
        threading.Thread(target=load_pdf_worker, args=(model, fname)).start()

# เริ่มโหลดทันทีที่รัน Script
start_preloading()

@app.route('/')
def home():
    return jsonify({
        "service": "X-tech Rama 2 Service Support",
        "system_status": load_status,
        "debug_paths": debug_paths,
        "cache_pages": {m: len(pdf_content_cache[m]) for m in pdf_content_cache}
    })

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    model = data.get('model', 'G6').upper()
    
    if not query or not pdf_content_cache.get(model):
        return jsonify([])

    results = []
    search_q = query.replace(" ", "").lower()
    
    for idx, text in enumerate(pdf_content_cache[model]):
        clean_text = text.replace(" ", "").lower()
        if search_q in clean_text:
            # พยายามหาตำแหน่งเพื่อทำ Snippet
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
    model = model.upper()
    filename = "การใช้งานหน้าจอ.pdf" if model == "SCREEN" else f"{model}.pdf"
    path = find_pdf_path(filename)
    
    target_page = request.args.get('page', default=1, type=int)
    if not os.path.exists(path): return f"File not found: {path}", 404
    
    try:
        with fitz.open(path) as doc:
            current_idx = target_page - 1
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
        return str(e), 500

if __name__ == '__main__':
    # สำหรับรัน Local ทดสอบ
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)