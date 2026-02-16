from fastapi import FastAPI, UploadFile, File, HTTPException

app = FastAPI(title="report explainer - report overview api", version="0.1.0")

MAX_MB = 20
MAX_BYTES = MAX_MB * 1024 * 1024


@app.get("/health")
def health():
    return {"status": "ok"}


def is_pdf(file: UploadFile) -> bool:
    name_ok = (file.filename or "").lower().endswith(".pdf")
    mime_ok = (file.content_type or "").lower() == "application/pdf"
    return name_ok or mime_ok


@app.post("/api/report-overview/upload")
async def upload_report(file: UploadFile = File(...)):
    # validate pdf
    if not is_pdf(file):
        raise HTTPException(status_code=400, detail="only pdf files are allowed")

    content = await file.read()

    # validate size
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"file too large. max {MAX_MB}mb")

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="empty file")

    # delete report variable (lower memory)
    content = b""

    return {
        "is_valid_report": True,
        "message": "upload validated. next step: pdf parsing + rag + openai",
        "tests_detected": ["CHOL", "LDL", "HDL", "TG"],
        "warnings": ["mvp stub response"]
    }
