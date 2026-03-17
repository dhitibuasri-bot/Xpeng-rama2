import os
import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io

app = Flask(__name__)
CORS(app)

# --- Memory Cache สำหรับเก็บข้อความใน PDF ---
pdf_content_cache = {"G6": [], "X9": []}

def clean_thai_text(text):
    if not text: return ""
    # แก้ปัญหา ก า ร ท า -> การทำ
    text = re.sub(r'(?<=[\u0e00-\u0e7f])\s+(?=[\u0e00-\u0e7f])', '', text)
    text = text.replace('\n', ' ')
    return re.sub(r'\s+', ' ', text).strip()

def get_manual_path(model):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.join(current_dir, "manuals")
    model_upper = model.upper()
    if model_upper not in ["G6", "X9"]: return None
    
    filename = f"{model_upper}.pdf"
    full_path = os.path.join(base_dir, filename)
    return full_path if os.path.exists(full_path) else None

def load_all_manuals():
    """โหลดข้อความจาก PDF ทั้งหมดเข้า Cache เมื่อ Start Server"""
    for model in ["G6", "X9"]:
        path = get_manual_path(model)
        if path:
            try:
                with fitz.open(path) as doc:
                    for page_num in range(len(doc)):
                        page = doc.load_page(page_num)
                        text = clean_thai_text(page.get_text("text"))
                        pdf_content_cache[model].append(text)
                print(f"Loaded {model} manual: {len(pdf_content_cache[model])} pages.")
            except Exception as e:
                print(f"Error loading {model}: {e}")

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "XPENG Assistant API - Thai Fixed & Range Viewer"})

@app.route('/view/<model>')
def view_pdf(model):
    path = get_manual_path(model)
    target_page = request.args.get('page', default=1, type=int)
    if not path: return "File not found", 404

    try:
        with fitz.open(path) as doc:
            total_pages = len(doc)
            # ปรับเป็น 0-indexed
            current_idx = target_page - 1
            
            # --- คำนวณช่วงหน้า (ดึงหน้าเป้าหมาย +- 2 หน้า รวมเป็น 5 หน้า) ---
            start_page = max(0, current_idx - 2)
            end_page = min(total_pages - 1, current_idx + 2)
            
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page)
            pdf_bytes = new_doc.write()
            new_doc.close()

            output = io.BytesIO(pdf_bytes)
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/pdf',
                as_attachment=False,
                download_name=f"{model}_pages_{start_page+1}-{end_page+1}.pdf"
            )
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    model = data.get('model', 'G6').upper()
    
    if not query or model not in pdf_content_cache:
        return jsonify([])

    results = []
    # ลบช่องว่างในคำค้นหาเพื่อให้หาเจอแม้อักษรใน PDF จะเว้นวรรค
    search_q = query.replace(" ", "").lower()

    for idx, clean_text in enumerate(pdf_content_cache[model]):
        # ตรวจสอบแบบไม่สนช่องว่าง
        if search_q in clean_text.replace(" ", "").lower():
            # พยายามหาตำแหน่งเพื่อทำ Snippet
            found_idx = clean_text.lower().find(query.lower())
            if found_idx == -1: 
                found_idx = 0 
            
            start = max(0, found_idx - 60)
            snippet = clean_text[start:start+250]
            
            results.append({
                "page": idx + 1,
                "text": f"...{snippet.strip()}...",
                "model": model
            })
            
        if len(results) >= 15: break
            
    return jsonify(results)

if __name__ == '__main__':
    load_all_manuals()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)