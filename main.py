import os
import re
import fitz
from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

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

@app.route('/')
def home():
    return jsonify({"status": "online"})

@app.route('/view/<model>')
def view_pdf(model):
    path = get_manual_path(model)
    if not path: return "File not found", 404
    
    # ใช้ send_from_directory ที่รองรับ Conditional Requests (Byte Ranges) โดยธรรมชาติ
    response = make_response(send_from_directory(
        os.path.dirname(path), 
        os.path.basename(path)
    ))
    
    # บังคับ Header เพื่อให้ Browser พยายามเปิดที่หน้าต้นทาง
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline'
    response.headers['Accept-Ranges'] = 'bytes' # บอก Browser ว่า "ขอโหลดแค่บางส่วนของไฟล์ได้นะ"
    return response

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    query = data.get('query', '').strip()
    model = data.get('model', 'G6').upper()
    if not query: return jsonify([])

    path = get_manual_path(model)
    if not path: return jsonify([])

    results = []
    search_q = query.replace(" ", "").lower()

    try:
        with fitz.open(path) as doc:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text("text")
                clean_text = clean_thai_text(text)
                if search_q in clean_text.replace(" ", "").lower():
                    found_idx = clean_text.lower().find(query.lower())
                    start = max(0, found_idx - 60)
                    results.append({
                        "page": page_num + 1,
                        "text": f"...{clean_text[start:start+250]}...",
                        "model": model
                    })
                if len(results) >= 15: break
        return jsonify(results)
    except:
        return jsonify([])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)