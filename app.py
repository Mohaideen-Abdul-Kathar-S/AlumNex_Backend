


import os
import io
import json
from typing import Dict, Any

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

import google.generativeai as genai
from PyPDF2 import PdfReader
from io import BytesIO

from pymongo import MongoClient
import gridfs
from bson import ObjectId

import pytesseract

# On Render (Linux), tesseract is in PATH after apt install, so no need for manual path
# On Windows (local), keep your path
import platform
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# ---------------------------
# 🔑 Configure Gemini
# ---------------------------
API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAG9StpoICv_50dixmD8c9gSc_M_bEwGg0")
genai.configure(api_key=API_KEY)

model = genai.GenerativeModel(
    "gemini-1.5-flash",
    generation_config={"response_mime_type": "application/json"}
)

# ---------------------------
# 🚀 FastAPI app + CORS
# ---------------------------
app = FastAPI(title="Resume Parser with Gemini + MongoDB")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# 📦 MongoDB setup
# ---------------------------
try:
    # Get from environment variable
    MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://mohaideenabdulkathars23csd:DzSbHU79AfKPkOk6@cluster0.8v7rv29.mongodb.net/alumnex?retryWrites=true&w=majority&appName=Cluster0")
    
    client = MongoClient(MONGO_URI)
    db = client["alumnex"]   # your DB name
    fs = gridfs.GridFS(db)
    print("✅ MongoDB connected successfully!")
except Exception as e:
    print("❌ Failed to connect to MongoDB:", e)

# ---------------------------
# 🧠 Helper: extract text from PDF
# ---------------------------
def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(file_bytes))
        text_parts = []
        for page in reader.pages:
            t = page.extract_text() or ""
            text_parts.append(t)
        return "\n".join(text_parts).strip()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read PDF: {e}")

# ---------------------------
# 🎯 Fields
# ---------------------------
FIELDS = [
    "Full Name", "Email", "Skills", "Currently Studying", "Gender",
    "Phone Number", "Location", "Program Branch", "Batch", "Preferred Role",
    "Higher Studies", "Dream Company", "Technical Skills", "Certification",
    "Projects", "Clubs", "Domain", "Current Job", "Company",
    "Experience Year", "Working In"
]

# ---------------------------
# 🧾 Upload + Parse Endpoint
# ---------------------------
@app.post("/upload-resume")
async def upload_resume(user_id: str = Form(...), file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    file_bytes = await file.read()

    # 🔹 Delete old resume if exists
    old_user = db.users.find_one({"_id": user_id})
    if old_user and "resume" in old_user:
        try:
            fs.delete(ObjectId(old_user["resume"]))
        except:
            pass

    # 🔹 Save new resume to GridFS
    file_id = fs.put(file_bytes, filename=f"{user_id}_resume", content_type=file.content_type)

    # 🔹 Extract text
    resume_text = extract_text_from_pdf(file_bytes)
    if not resume_text:
        raise HTTPException(status_code=422, detail="No extractable text found in PDF.")

    # 🔹 Ask Gemini to parse
    prompt = f"""
You are a resume parser. Return JSON with EXACTLY these keys:
{FIELDS}

Rules:
- If unknown, use "".
- Skills/Technical Skills: comma-separated string.
- Projects/Clubs: semicolon-separated string.
Return JSON ONLY.

Resume Text:
{resume_text}
"""
    try:
        resp = model.generate_content(prompt)
        parsed = json.loads(resp.text)

        for k in FIELDS:
            parsed.setdefault(k, "")

        # 🔹 Save parsed fields + resume reference into MongoDB
        db.users.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "resume": str(file_id),
                    "fields": parsed
                }
            },
            upsert=True
        )

        return {
            "message": "Resume uploaded and parsed successfully",
            "file_id": str(file_id),
            "parsed_fields": parsed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {e}")


@app.get("/get-resume/{user_id}")
def get_resume(user_id: str):
    user = db.users.find_one({"_id": user_id})
    if not user or "resume" not in user:
        return JSONResponse(content={"message": "Resume not found"}, status_code=404)

    file_id = ObjectId(user["resume"])
    file = fs.get(file_id)

    return StreamingResponse(
        io.BytesIO(file.read()),
        media_type=file.content_type,
        headers={"Content-Disposition": f"attachment; filename={file.filename}"}
    )

import io
from PyPDF2 import PdfReader
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image

def extract_text_from_IDcard_file(file_bytes: bytes) -> str:
    text = ""

    # ---------- Try as PDF ----------
    try:
        pdf = PdfReader(io.BytesIO(file_bytes))
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        if text.strip():
            return text.strip()

        # ---------- Fall back to OCR on PDF ----------
        images = convert_from_bytes(file_bytes)  # Convert PDF pages to images
        ocr_text = ""
        for img in images:
            ocr_text += pytesseract.image_to_string(img) + "\n"

        return ocr_text.strip()

    except Exception as pdf_error:
        print(f"⚠️ Not a valid PDF, trying image OCR: {pdf_error}")

    # ---------- Try as Image ----------
    try:
        image = Image.open(io.BytesIO(file_bytes))
        ocr_text = pytesseract.image_to_string(image)
        return ocr_text.strip()
    except Exception as img_error:
        print(f"⚠️ Image extraction failed: {img_error}")
        return ""
import traceback
from fastapi import UploadFile, File, HTTPException

@app.post("/parse_id_card")
async def parse_id_card(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()

        extracted_text = extract_text_from_IDcard_file(file_bytes)
        if not extracted_text:
            raise HTTPException(status_code=400, detail="No text could be extracted from the file.")

        prompt = f"""
        You are a smart ID card parser. 
        From the given student ID card text, extract the following details in JSON:
        - College Name
        - Student Name
        - Student Roll No
        - Student Batch
        - Date of Birth (optional, if available)

        If any field is missing, return null for that field.

        ID Card text:
        {extracted_text}
        """

        response = model.generate_content(prompt)

        structured_data = None
        if hasattr(response, "output_text") and response.output_text:
            structured_data = response.output_text.strip()
        elif hasattr(response, "text") and response.text:
            structured_data = response.text.strip()
        elif hasattr(response, "candidates") and response.candidates:
            structured_data = (
                response.candidates[0].content.parts[0].text.strip()
            )
        else:
            raise ValueError("Gemini returned an unexpected response format")

        try:
            structured_data_json = json.loads(structured_data)
        except Exception:
            structured_data_json = {"raw_text": structured_data}

        print(f"✅ Structured Data: {structured_data_json}")
        return {"status": "success", "data": structured_data_json}

    except Exception as e:
        print("❌ Backend Error:", str(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error parsing ID card: {str(e)}")


@app.post("/parse_id_card")
async def parse_id_card(file: UploadFile = File(...)):
    ...
    structured_data = json.loads(response.text.strip())
    
    # Save to MongoDB
    result = db.idcards.insert_one(structured_data)
    structured_data["_id"] = str(result.inserted_id)

    return {"status": "success", "data": structured_data}


# .venv\Scripts\Activate.ps1
# uvicorn app:app --reload --host 0.0.0.0 --port 8000