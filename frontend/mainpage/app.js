// pdf only + 20mb max
const MAX_MB = 20;
const MAX_BYTES = MAX_MB * 1024 * 1024;

const fileInput = document.getElementById("pdfFile");
const errorBox = document.getElementById("errorBox");
const submitBtn = document.getElementById("submitBtn");
const form = document.getElementById("uploadForm");

function setError(message) {
  errorBox.textContent = message || "";
}

function validateFile(file) {
  if (!file) {
    setError("please select a pdf file.");
    submitBtn.disabled = true;
    return false;
  }

  const isPdfMime = file.type === "application/pdf";
  const isPdfExt = file.name.toLowerCase().endsWith(".pdf");

  if (!isPdfMime && !isPdfExt) {
    setError("only pdf files are allowed.");
    submitBtn.disabled = true;
    return false;
  }

  if (file.size > MAX_BYTES) {
    setError(`file is too large. max allowed is ${MAX_MB}mb.`);
    submitBtn.disabled = true;
    return false;
  }

  setError("");
  submitBtn.disabled = false;
  return true;
}

fileInput.addEventListener("change", (e) => {
  const file = e.target.files?.[0];
  validateFile(file);
});

form.addEventListener("submit", (e) => {
  e.preventDefault();

  const file = fileInput.files?.[0];
  if (!validateFile(file)) return;

  // for now, we just confirm the upload is valid
  // later, we will call backend/report-overview upload api
  alert("file validated. next: connect to upload api.");
});
