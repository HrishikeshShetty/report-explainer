from __future__ import annotations

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import pandas as pd
import math
import re
import io
import pdfplumber

app = FastAPI(title="report explainer - report overview api", version="0.1.0")

# CORS (optional – keep if you're calling from frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Config
# -----------------------------
MAX_MB = 30
MAX_BYTES = MAX_MB * 1024 * 1024

# app/main.py -> app/
BASE_DIR = Path(__file__).resolve().parent  # app/
DATA_DIR = BASE_DIR / "data"               # app/data

# Pick ONE file as your lipid reference source.
LIPID_REF_PATH = DATA_DIR / "rag_lipid_reference_CHOL_LDL_HDL_TG.csv"
# If you're using the other file instead, change to:
# LIPID_REF_PATH = DATA_DIR / "ReportExplainer_refineddataset.csv"

lipid_df: pd.DataFrame | None = None
lipid_load_error: str | None = None

# -----------------------------
# Lipid Detection (MVP)
# -----------------------------
LIPID_PATTERNS = {
    # Matches examples:
    # "CHOL 5.22", "Total Cholesterol: 210", "Cholesterol - 210"
    "CHOL": r"\b(?:chol|cholesterol|total\s*cholesterol)\b\s*[:\-]?\s*(\d+(?:\.\d+)?)",

    # Matches:
    # "LDL 140", "LDL Cholesterol: 140"
    "LDL": r"\b(?:ldl|ldl\s*cholesterol)\b\s*[:\-]?\s*(\d+(?:\.\d+)?)",

    # Matches:
    # "HDL 45", "HDL Cholesterol: 45"
    "HDL": r"\b(?:hdl|hdl\s*cholesterol)\b\s*[:\-]?\s*(\d+(?:\.\d+)?)",

    # Matches:
    # "TG 180", "Triglycerides: 180", "Triglyceride - 180"
    "TG": r"\b(?:tg|triglycerides?|triglyceride)\b\s*[:\-]?\s*(\d+(?:\.\d+)?)",
}


def detect_lipids_from_text(text: str) -> dict:
    """
    Simple regex-based lipid detector (MVP).
    Returns dict like: {"CHOL": 210.0, "LDL": 130.0}
    """
    results: dict[str, float] = {}
    lowered = (text or "").lower()

    for lipid, pattern in LIPID_PATTERNS.items():
        match = re.search(pattern, lowered)
        if match:
            try:
                results[lipid] = float(match.group(1))  # <-- CHANGED to group(1)
            except Exception:
                pass

    return results


# -----------------------------
# Helpers
# -----------------------------
def extract_text_from_pdf_bytes(pdf_bytes: bytes, max_pages: int = 3) -> str:
    """
    Extract text from the first `max_pages` pages of a PDF (MVP).
    Keeps it limited so it’s fast and safe.
    """
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages[:max_pages]:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text)
    return "\n\n".join(text_parts).strip()


def to_json_safe(value):
    """
    Convert pandas/numpy NaN to None so JSON serialization doesn't crash.
    """
    if value is None:
        return None
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
    except Exception:
        pass
    if pd.isna(value):
        return None
    return value


def df_to_json_safe_records(df: pd.DataFrame) -> list[dict]:
    """
    Convert dataframe records to JSON safe list[dict] (NaN -> None).
    """
    records = df.to_dict(orient="records")
    cleaned = []
    for row in records:
        cleaned.append({k: to_json_safe(v) for k, v in row.items()})
    return cleaned


def load_lipid_reference():
    """
    Load lipid reference CSV once at startup.
    """
    global lipid_df, lipid_load_error
    try:
        if not LIPID_REF_PATH.exists():
            lipid_df = None
            lipid_load_error = f"CSV not found at: {LIPID_REF_PATH}"
            return

        df = pd.read_csv(LIPID_REF_PATH)
        df.columns = [c.strip() for c in df.columns]

        lipid_df = df
        lipid_load_error = None
    except Exception as e:
        lipid_df = None
        lipid_load_error = str(e)


@app.on_event("startup")
def on_startup():
    load_lipid_reference()


# -----------------------------
# Routes
# -----------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/report-overview/upload")
async def upload_report(file: UploadFile = File(...)):
    # basic validations
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()

    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"file too large. max {MAX_MB}mb")

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="empty file")

    # REAL extraction (MVP): first 3 pages only
    extracted_text = extract_text_from_pdf_bytes(content, max_pages=3)

    # keep preview short for swagger readability
    text_preview = extracted_text[:1500] if extracted_text else ""

    # detect lipids from extracted text
    detected_lipids = detect_lipids_from_text(extracted_text)

    # free memory
    content = b""

    return {
        "is_valid_report": True,
        "message": "pdf uploaded and text extracted",
        "text_preview": text_preview,
        "detected_lipids": detected_lipids,
        "warnings": ["mvp: extraction only, rag + llm next"],
    }


@app.get("/api/report-overview/reference/lipids")
def lipid_reference_sample():
    if lipid_df is None:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "lipid dataset not loaded",
                "path": str(LIPID_REF_PATH),
                "error": lipid_load_error,
            },
        )

    sample = lipid_df.head(25).copy()

    return {
        "source": str(LIPID_REF_PATH.name),
        "rows_returned": int(len(sample)),
        "columns": list(sample.columns),
        "data": df_to_json_safe_records(sample),
    }
