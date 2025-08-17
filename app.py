# import os
# from typing import Dict, Any

# from fastapi import FastAPI, File, UploadFile, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse

# import google.generativeai as genai
# from PyPDF2 import PdfReader
# from io import BytesIO

# # ---------------------------
# # 🔑 Configure Gemini
# # ---------------------------
# API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAG9StpoICv_50dixmD8c9gSc_M_bEwGg0")
# if not API_KEY:
#     raise RuntimeError("Set GEMINI_API_KEY environment variable before starting the server.")
# genai.configure(api_key=API_KEY)

# model = genai.GenerativeModel(
#     "gemini-1.5-flash",
#     generation_config={"response_mime_type": "application/json"}
# )

# # ---------------------------
# # 🚀 FastAPI app + CORS
# # ---------------------------
# app = FastAPI(title="Resume Parser via Gemini", version="1.0")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # adjust for your domain in production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ---------------------------
# # 🧠 Helper: extract text from PDF
# # ---------------------------
# def extract_text_from_pdf(file_bytes: bytes) -> str:
#     try:
#         reader = PdfReader(BytesIO(file_bytes))
#         text_parts = []
#         for page in reader.pages:
#             # NOTE: scanned PDFs may return None; OCR can be added later
#             t = page.extract_text() or ""
#             text_parts.append(t)
#         text = "\n".join(text_parts).strip()
#         return text
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Failed to read PDF: {e}")

# # ---------------------------
# # 🎯 Fields we want (customize freely)
# # ---------------------------
# FIELDS = [
#     "Full Name",
#     "Email",
#     "Skills",
#     "Currently Studying",
#     "Gender",
#     "Phone Number",
#     "Location",
#     "Program Branch",
#     "Batch",
#     "Preferred Role",
#     "Higher Studies",
#     "Dream Company",
#     "Technical Skills",
#     "Certification",
#     "Projects",
#     "Clubs",
#     "Domain",
#     "Current Job",
#     "Company",
#     "Experience Year",
#     "Working In"
# ]

# # ---------------------------
# # 🧾 Endpoint: POST /parse
# # ---------------------------
# @app.post("/parse")
# async def parse_resume(file: UploadFile = File(...)) -> Dict[str, Any]:
#     if not file.filename.lower().endswith(".pdf"):
#         raise HTTPException(status_code=400, detail="Please upload a PDF file.")

#     file_bytes = await file.read()
#     resume_text = extract_text_from_pdf(file_bytes)
#     if not resume_text:
#         raise HTTPException(
#             status_code=422,
#             detail="No extractable text found in the PDF. If it's a scanned image, add OCR."
#         )

#     # Ask Gemini to return STRICT JSON with the fields above
#     schema_example = {k: "" for k in FIELDS}
#     prompt = f"""
# You are a resume parser. Read the resume text and return a strict JSON object with EXACTLY these keys:

# {FIELDS}

# Rules:
# - If a field is unknown or not found, use an empty string "".
# - For "Skills" or "Technical Skills", return a comma-separated string (not an array).
# - For "Projects" and "Clubs", return a semicolon-separated string if multiple.
# - Do NOT include any keys other than the ones listed.
# - Do NOT add explanations.

# Return JSON ONLY.

# Resume Text:
# {resume_text}
# """

#     try:
#         resp = model.generate_content(prompt)
#         # resp.text should be pure JSON because of response_mime_type
#         # but we still guard against empty/invalid response
#         text = (resp.text or "").strip()
#         if not text:
#             raise ValueError("Empty response from Gemini.")
#         # FastAPI will validate/pretty-print JSON automatically if we load it
#         # But Gemini already returns JSON as text; to be safe, let FastAPI check.
#         import json
#         data = json.loads(text)

#         # Ensure all expected keys exist
#         for k in FIELDS:
#             data.setdefault(k, "")

#         return JSONResponse(content=data)

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Gemini error: {e}")

# @app.get("/health")
# def health():
#     return {"status": "ok"}





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
    client = MongoClient("mongodb://localhost:27017")
    db = client["alumnex"]
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

# .venv\Scripts\Activate.ps1
# uvicorn app:app --reload --host 0.0.0.0 --port 8000