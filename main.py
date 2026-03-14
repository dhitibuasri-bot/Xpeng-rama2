import os
import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

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
    return jsonify({"status": "online", "message": "XPENG Assistant API is running"})

@app.route('/view/<model>')
def view_pdf(model):
    path = get_manual_path(model)
    if not path: return "ไม่พบไฟล์", 404
    
    # ส่งไฟล์และบังคับ Header ให้รองรับ Byte Ranges (ช่วยเรื่องการโหลดหน้า PDF)
    response = make_response(send_from_directory(
        os.path.dirname(path), 
        os.path.basename(path),
        mimetype='application/pdf'
    ))
    response.headers['Accept-Ranges'] = 'bytes'
    return response

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    if not data: return jsonify([])
    
    query = data.get('query', '').strip()
    model = data.get('model', 'G6').upper()
    
    if not query: return jsonify([])
    path = get_manual_path(model)
    if not path: return jsonify({"error": "Model path not found"}), 404

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
                    snippet = clean_text[start:start+300]
                    
                    results.append({
                        "page": page_num + 1,
                        "text": f"...{snippet.strip()}...",
                        "model": model
                    })
                if len(results) >= 15: break
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)