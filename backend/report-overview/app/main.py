from __future__ import annotations

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import pandas as pd
import math

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
MAX_MB = 10
MAX_BYTES = MAX_MB * 1024 * 1024

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/report-overview
DATA_DIR = BASE_DIR / "data"

# Pick ONE file as your lipid reference source.
# Update this filename to match the file you want:
LIPID_REF_PATH = DATA_DIR / "rag_lipid_reference_CHOL_LDL_HDL_TG.csv"
# If you're using the other file instead, change to:
# LIPID_REF_PATH = DATA_DIR / "ReportExplainer_refineddataset.csv"

lipid_df: pd.DataFrame | None = None
lipid_load_error: str | None = None


# -----------------------------
# Helpers
# -----------------------------
def to_json_safe(value):
    """
    Convert pandas/numpy NaN to None so JSON serialization doesn't crash.
    """
    # Handles float('nan') and numpy.nan
    if value is None:
        return None
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
    except Exception:
        pass
    # pandas sometimes gives <NA> / NaT types
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

        # Optional cleanup: strip column names
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

    # MVP stub: just pretend we extracted text
    # (replace with real pdf parsing later)
    text_preview = f"{file.filename} uploaded ({len(content)} bytes)"

    # free memory
    content = b""

    return {
        "is_valid_report": True,
        "message": "pdf uploaded and text extracted",
        "text_preview": text_preview,
        "warnings": ["mvp: extraction only, rag + openai next"],
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

    # return a small sample so swagger doesn't show huge output
    sample = lipid_df.head(25).copy()

    return {
        "source": str(LIPID_REF_PATH.name),
        "rows_returned": int(len(sample)),
        "columns": list(sample.columns),
        "data": df_to_json_safe_records(sample),
    }
