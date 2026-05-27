from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

import fitz
import os
import re
import gspread

from rapidfuzz import fuzz

from datetime import datetime

from oauth2client.service_account import (
    ServiceAccountCredentials
)

# =========================
# FLASK
# =========================

app = Flask(__name__)

CORS(app)

# =========================
# CONFIG
# =========================

PDF_FOLDER = "manuals"

pdf_content_cache = {}

# =========================
# GOOGLE SHEETS
# =========================

scope = [

    "https://spreadsheets.google.com/feeds",

    "https://www.googleapis.com/auth/drive"

]

creds = ServiceAccountCredentials.from_json_keyfile_name(

    "credentials.json",

    scope

)

client = gspread.authorize(creds)

sheet = client.open(
    "XPENG Referral"
).sheet1

# =========================
# SYNONYMS
# =========================

SYNONYMS = {

    "แคมป์": [

        "camp",
        "camp mode",
        "sleep mode",
        "พัก"

    ],

    "ลมยาง": [

        "psi",
        "pressure",
        "tire pressure"

    ],

    "ชาร์จ": [

        "charging",
        "charger",
        "battery"

    ],

    "หน้าจอ": [

        "screen",
        "display"

    ],

    "กุญแจ": [

        "key",
        "smart key"

    ]

}

# =========================
# CLEAN TEXT
# =========================

def clean_text(text):

    text = text.replace(
        "\n",
        " "
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()

# =========================
# HIGHLIGHT
# =========================

def highlight_text(text, keyword):

    pattern = re.compile(

        re.escape(keyword),

        re.IGNORECASE

    )

    return pattern.sub(

        lambda m:
        f"<mark>{m.group(0)}</mark>",

        text

    )

# =========================
# LOAD PDF
# =========================

print("\n🔥 Loading PDF manuals...\n")

for filename in os.listdir(PDF_FOLDER):

    if filename.endswith(".pdf"):

        path = os.path.join(

            PDF_FOLDER,

            filename

        )

        print(f"📄 Loading {filename}")

        doc = fitz.open(path)

        pages = []

        for page_num, page in enumerate(doc):

            text = clean_text(

                page.get_text()

            )

            pages.append({

                "page": page_num + 1,

                "text": text

            })

        model_name = filename.replace(
            ".pdf",
            ""
        )

        pdf_content_cache[
            model_name
        ] = pages

print("\n✅ PDF Loaded Successfully\n")

# =========================
# HOME
# =========================

@app.route("/")
def home():

    return send_from_directory(

        ".",

        "index.html"

    )

# =========================
# STATIC
# =========================

@app.route("/static/<path:path>")
def static_files(path):

    return send_from_directory(

        "static",

        path

    )

# =========================
# SEARCH
# =========================

@app.route(
    "/search",
    methods=["POST"]
)
def search():

    data = request.json

    query = data.get(

        "query",

        ""

    ).lower()

    selected_model = data.get(

        "model",

        ""

    )

    expanded_queries = [query]

    for key, values in SYNONYMS.items():

        if key in query:

            expanded_queries.extend(values)

    results = []

    # =========================
    # SEARCH PDF
    # =========================

    for model, pages in pdf_content_cache.items():

        if selected_model:

            if model.lower() != selected_model.lower():

                continue

        for page_data in pages:

            content = page_data["text"].lower()

            best_score = 0

            matched_query = ""

            for q in expanded_queries:

                score = fuzz.partial_ratio(

                    q,

                    content

                )

                if score > best_score:

                    best_score = score

                    matched_query = q

            if best_score > 70:

                snippet = page_data[
                    "text"
                ][:700]

                snippet = highlight_text(

                    snippet,

                    matched_query

                )

                results.append({

                    "model": model,

                    "page": page_data["page"],

                    "score": best_score,

                    "text": snippet

                })

    # =========================
    # SORT
    # =========================

    results = sorted(

        results,

        key=lambda x: x["score"],

        reverse=True

    )

    return jsonify(results[:10])

# =========================
# VIEW PDF WITH PAGE
# =========================

@app.route("/view/<model>")
def view_pdf(model):

    model = model.upper()

    page = request.args.get(
        "page",
        1
    )

    filename = f"{model}.pdf"

    pdf_url = f"/manuals/{filename}#page={page}"

    return f"""

    <!DOCTYPE html>

    <html>

    <head>

        <meta charset="UTF-8">

        <script>

            window.location.href = "{pdf_url}"

        </script>

    </head>

    <body>

        กำลังเปิด PDF...

    </body>

    </html>

    """

# =========================
# MANUAL FILES
# =========================

@app.route("/manuals/<path:filename>")
def manuals(filename):

    return send_from_directory(

        PDF_FOLDER,

        filename

    )

# =========================
# REFERRAL
# =========================

@app.route(
    "/referral",
    methods=["POST"]
)
def referral():

    data = request.json

    now = datetime.now().strftime(

        "%Y-%m-%d %H:%M:%S"

    )

    # =========================
    # SAVE TO GOOGLE SHEETS
    # =========================

    sheet.append_row([

        now,

        data.get("your_name"),

        data.get("your_phone"),

        data.get("friend_name"),

        data.get("friend_phone"),

        data.get("model"),

        data.get("note")

    ])

    print("\n🔥 NEW REFERRAL")

    print(data)

    return jsonify({

        "success": True

    })

# =========================
# HEALTH CHECK
# =========================

@app.route("/health")
def health():

    return jsonify({

        "status": "ok"

    })

# =========================
# RUN
# =========================

if __name__ == "__main__":

    app.run(

        debug=True,

        host="0.0.0.0",

        port=5000

    )