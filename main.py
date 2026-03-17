import os
import re
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io

app = Flask(__name__)
CORS(app)

# --- Global Cache สำหรับเก็บเนื้อหา PDF ---
pdf_content_cache = {"G6": [], "X9": []}

def clean_thai_text(text):
    if not text: return ""
    # แก้ปัญหาช่องว่างระหว่างตัวอักษรไทย เช่น "ก า ร" -> "การ"
    text = re.sub(r'(?<=[\u0e00-\u0e7f])\s+(?=[\u0e00-\u0e7f])', '', text)
    text = text.replace('\n', ' ')
    return re.sub(r'\s+', ' ', text).strip()

def load_pdf_to_cache(model):
    """ ฟังก์ชันโหลดไฟล์ PDF เข้า Memory พร้อมระบุชื่อหน่วยงาน X-tech """
    model = model.upper()
    path = os.path.join(os.getcwd(), "manuals", f"{model}.pdf")
    
    if os.path.exists(path):
        try:
            print(f"📖 X-tech System: กำลังโหลดไฟล์ {model} จาก {path}")
            with fitz.open(path) as doc:
                content = []
                for page in doc:
                    content.append(clean_thai_text(page.get_text()))
                pdf_content_cache[model] = content
            print(f"✅ X-tech System: โหลดสำเร็จ {model} ({len(content)} หน้า)")
            return True
        except Exception as e:
            print(f"❌ X-tech System Error: ไม่สามารถอ่านไฟล์ {model} ได้: {e}")
    else:
        print(f"⚠️ X-tech System Warning: ไม่พบไฟล์ที่ {path}")
    return False

# --- Routes ---

@app.route('/')
def home():
    """ หน้าแรกสำหรับเช็คสถานะ X-tech Rama 2 Service Support """
    # บังคับเช็ค Cache ทุกครั้งที่เข้าหน้า Home เพื่อป้องกันข้อมูลหลุด
    if not pdf_content_cache["G6"]: load_pdf_to_cache("G6")
    if not pdf_content_cache["X9"]: load_pdf_to_cache("X9")
    
    manuals_dir = os.path.join(os.getcwd(), "manuals")
    files_in_folder = os.listdir(manuals_dir) if os.path.exists(manuals_dir) else "Folder not found"
    
    return jsonify({
        "service": "X-tech Rama 2 Service Support",
        "system": "XPENG Assistant Search Engine",
        "status": "Ready",
        "cache_status": {m: f"{len(pdf_content_cache[m])} pages loaded" for m in pdf_content_cache},
        "debug_info": {
            "current_working_dir": os.getcwd(),
            "detected_files": files_in_folder
        }
    })

@app.route('/search', methods=['POST'])
def search():
    """ ค้นหาข้อความใน PDF สำหรับทีมเทคนิค """
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    model = data.get('model', 'G6').upper()
    
    # ตรวจสอบ Cache หากว่างให้โหลดทันที (On-demand)
    if not pdf_content_cache.get(model):
        load_pdf_to_cache(model)
        
    if not query or not pdf_content_cache.get(model):
        return jsonify([])

    results = []
    # ค้นหาแบบไม่สนช่องว่างเพื่อความแม่นยำในภาษาไทย
    search_q = query.replace(" ", "").lower()
    
    for idx, text in enumerate(pdf_content_cache[model]):
        if search_q in text.replace(" ", "").lower():
            # หาตำแหน่งคำเพื่อทำ Snippet สั้นๆ
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
    """ แสดงผลเฉพาะหน้า: หน้าก่อน 1 - หน้าเป้าหมาย - หน้าหลัง 1 """
    model = model.upper()
    path = os.path.join(os.getcwd(), "manuals", f"{model}.pdf")
    target_page = request.args.get('page', default=1, type=int)
    
    if not os.path.exists(path):
        return "File not found", 404

    try:
        with fitz.open(path) as doc:
            total_pages = len(doc)
            current_idx = target_page - 1 # เปลี่ยนเป็น 0-based index
            
            if current_idx < 0 or current_idx >= total_pages:
                return f"Page {target_page} out of range", 400

            # --- Logic ตัดหน้าตามโจทย์: หน้าก่อน 1 และ หน้าหลัง 1 ---
            start = max(0, current_idx - 1)
            end = min(total_pages - 1, current_idx + 1)
            
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=start, to_page=end)
            pdf_bytes = new_doc.write()
            new_doc.close()
            
            output = io.BytesIO(pdf_bytes)
            output.seek(0)
            
            # ส่งเป็นไฟล์ PDF ขนาดเล็ก (มี 1-3 หน้า) เพื่อความรวดเร็ว
            return send_file(
                output,
                mimetype='application/pdf',
                as_attachment=False,
                download_name=f"Xtech_Rama2_{model}_page_{target_page}.pdf"
            )
    except Exception as e:
        return f"X-tech System Error: {str(e)}", 500

# --- Start Server ---
# โหลดข้อมูลล่วงหน้าก่อนรับ Request
load_pdf_to_cache("G6")
load_pdf_to_cache("X9")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)