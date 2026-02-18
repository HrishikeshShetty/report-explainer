from __future__ import annotations

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import pandas as pd
import math
import re
import io
import os

import pdfplumber
from dotenv import load_dotenv

# ✅ Gemini SDK
import google.generativeai as genai


app = FastAPI(title="report explainer - report overview api", version="0.2.0")

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

# Lipid reference CSV (grounding)
LIPID_REF_PATH = DATA_DIR / "rag_lipid_reference_CHOL_LDL_HDL_TG.csv"

lipid_df: pd.DataFrame | None = None
lipid_load_error: str | None = None

# -----------------------------
# Env / Gemini
# -----------------------------
# Loads backend/report-overview/.env when uvicorn is started from backend/report-overview
load_dotenv()

# Prefer GEMINI_API_KEY, fallback to GOOGLE_API_KEY (some setups use this name)
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "AIzaSyDexCK0q5v6Ccj2plLsDBctxnOo77xWJjQ")).strip()

# Default model (you can change via .env)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()

gemini_enabled = False
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_enabled = True

# -----------------------------
# Lipid Detection (MVP)
# -----------------------------
LIPID_PATTERNS = {
    "CHOL": r"\b(?:chol|cholesterol|total\s*cholesterol)\b\s*[:\-]?\s*(\d+(?:\.\d+)?)",
    "LDL": r"\b(?:ldl|ldl\s*cholesterol)\b\s*[:\-]?\s*(\d+(?:\.\d+)?)",
    "HDL": r"\b(?:hdl|hdl\s*cholesterol)\b\s*[:\-]?\s*(\d+(?:\.\d+)?)",
    "TG": r"\b(?:tg|triglycerides?|triglyceride)\b\s*[:\-]?\s*(\d+(?:\.\d+)?)",
}


def detect_lipids_from_text(text: str) -> dict:
    results: dict[str, float] = {}
    lowered = (text or "").lower()

    for lipid, pattern in LIPID_PATTERNS.items():
        match = re.search(pattern, lowered)
        if match:
            try:
                results[lipid] = float(match.group(1))
            except Exception:
                pass

    return results


# -----------------------------
# Helpers
# -----------------------------
def extract_text_from_pdf_bytes(pdf_bytes: bytes, max_pages: int = 10) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages[:max_pages]:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text)
    return "\n\n".join(text_parts).strip()


def to_json_safe(value):
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
    records = df.to_dict(orient="records")
    cleaned = []
    for row in records:
        cleaned.append({k: to_json_safe(v) for k, v in row.items()})
    return cleaned


def load_lipid_reference():
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


def get_grounding_rows_for_detected_lipids(detected: dict) -> list[dict]:
    """
    Pull the matching lipid rows from the reference CSV for grounding.
    """
    if lipid_df is None or not detected:
        return []

    # Expecting a "test_code" column in rag_lipid_reference_CHOL_LDL_HDL_TG.csv
    if "test_code" not in lipid_df.columns:
        return []

    codes = set(detected.keys())
    subset = lipid_df[lipid_df["test_code"].astype(str).str.upper().isin(codes)].copy()

    # Keep only a few columns to reduce prompt size (MVP)
    keep_cols = [
        "test_code",
        "test_name",
        "unit",
        "desirable_range",
        "borderline_high_range",
        "high_range",
        "low_range",
        "what_it_measures_plain",
        "how_to_read_results_plain",
        "if_high_may_mean_plain",
        "if_low_may_mean_plain",
        "safe_next_step_plain",
    ]
    keep_cols = [c for c in keep_cols if c in subset.columns]
    subset = subset[keep_cols].head(10)

    return df_to_json_safe_records(subset)


def generate_ai_overview(
    extracted_text: str,
    detected_lipids: dict,
    grounding_rows: list[dict],
) -> dict:
    """
    Calls Gemini to produce a short, simple overview grounded in the CSV rows.
    Returns a dict so we can add extra metadata later.
    """
    if not gemini_enabled:
        return {
            "enabled": False,
            "message": "GEMINI_API_KEY not set. AI overview disabled.",
            "overview": None,
            "model": GEMINI_MODEL,
        }

    # Keep prompt small & safe
    text_snippet = (extracted_text or "")[:2500]

    system_rules = (
        "You are Report Explainer. You help users understand lipid panel results in simple language.\n"
        "Rules:\n"
        "- Use ONLY the provided grounding reference data and the extracted report text.\n"
        "- If a detail is not present, say 'Not found in the report' or 'Not available in the reference'.\n"
        "- Do not provide diagnosis. Provide educational explanation only.\n"
        "- Keep it short and clear (5-8 bullet points max).\n"
    )

    user_payload = {
        "detected_lipids": detected_lipids,
        "reference_data": grounding_rows,
        "extracted_report_text_snippet": text_snippet,
        "task": (
            "Write a simple overview of the lipid results. "
            "If values exist, mention each test and explain what it means, desirable range, and a safe next step."
        ),
    }

    prompt = (
        f"{system_rules}\n"
        "INPUT (JSON-like):\n"
        f"{user_payload}\n"
        "\nOUTPUT:\n"
    )

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        resp = model.generate_content(prompt)

        overview_text = getattr(resp, "text", None) or "AI overview could not be generated."

        return {
            "enabled": True,
            "message": "AI overview generated",
            "overview": overview_text.strip(),
            "model": GEMINI_MODEL,
        }

    except Exception as e:
        err = str(e).lower()

        # basic quota/rate handling
        if "quota" in err or "rate" in err or "429" in err:
            return {
                "enabled": False,
                "message": "AI disabled: Gemini quota/rate limit hit",
                "overview": None,
                "model": GEMINI_MODEL,
                "error": "quota_or_rate_limit",
            }

        return {
            "enabled": False,
            "message": "AI overview failed",
            "overview": None,
            "model": GEMINI_MODEL,
            "error": str(e),
        }


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
    # validations
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()

    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"file too large. max {MAX_MB}mb")

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="empty file")

    # Extract text (first 10 pages)
    extracted_text = extract_text_from_pdf_bytes(content, max_pages=10)
    text_preview = extracted_text[:1500] if extracted_text else ""

    # Detect lipids
    detected_lipids = detect_lipids_from_text(extracted_text)

    # Grounding from CSV
    grounding_rows = get_grounding_rows_for_detected_lipids(detected_lipids)

    # AI overview (Gemini)
    ai_overview = generate_ai_overview(
        extracted_text=extracted_text,
        detected_lipids=detected_lipids,
        grounding_rows=grounding_rows,
    )

    # free memory
    content = b""

    return {
        "is_valid_report": True,
        "message": "pdf uploaded and text extracted",
        "text_preview": text_preview,
        "detected_lipids": detected_lipids,
        "grounding_rows": grounding_rows,
        "ai_overview": ai_overview,
        "warnings": ["mvp: educational only; not medical advice"],
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
