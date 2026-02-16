from fastapi import FastAPI, UploadFile, File, HTTPException
import fitz  # pymupdf

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


def extract_pdf_text(pdf_bytes: bytes) -> str:
    text_parts: list[str] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text("text"))
    return "\n".join(text_parts).strip()


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

    extracted_text = extract_pdf_text(content)
    if not extracted_text:
        raise HTTPException(status_code=400, detail="could not extract text from pdf")

    # delete report variable
    content = b""

    return {
        "is_valid_report": True,
        "message": "pdf uploaded and text extracted",
        "text_preview": extracted_text[:500],
        "warnings": ["mvp: extraction only, rag + openai next"],
    }
