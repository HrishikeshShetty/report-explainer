// pdf only + 20mb max (frontend validation)
const MAX_MB = 20;
const MAX_BYTES = MAX_MB * 1024 * 1024;

// backend
const API_BASE = "http://127.0.0.1:8000";
const UPLOAD_URL = `${API_BASE}/api/report-overview/upload`;

const fileInput = document.getElementById("pdfFile");
const errorBox = document.getElementById("errorBox");
const submitBtn = document.getElementById("submitBtn");
const form = document.getElementById("uploadForm");

// ---- UI helpers ----
function setError(message) {
  errorBox.textContent = message || "";
}

function setLoading(isLoading) {
  submitBtn.disabled = isLoading;
  submitBtn.textContent = isLoading ? "uploading..." : "continue";
}

function ensureResultsContainer() {
  let el = document.getElementById("results");
  if (el) return el;

  // insert after the form divider (simple)
  const divider = document.querySelector(".divider");
  el = document.createElement("div");
  el.id = "results";
  el.style.marginTop = "16px";
  divider?.insertAdjacentElement("afterend", el);

  return el;
}

function escapeHtml(str) {
  return String(str ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderJsonBlock(title, obj) {
  const safe = escapeHtml(JSON.stringify(obj, null, 2));
  return `
    <div style="margin-top:14px; padding:12px; border:1px solid rgba(255,255,255,0.12); border-radius:12px; background: rgba(255,255,255,0.04);">
      <div style="font-weight:700; margin-bottom:8px;">${escapeHtml(title)}</div>
      <pre style="white-space:pre-wrap; margin:0; color:#e9eefc; font-size:12px; line-height:1.5;">${safe}</pre>
    </div>
  `;
}

function renderDetectedLipids(detected) {
  const entries = Object.entries(detected || {});
  if (!entries.length) {
    return `<p style="color:var(--muted); margin:0;">No lipids detected in the text.</p>`;
  }

  const pills = entries
    .map(([k, v]) => {
      return `
        <span style="display:inline-flex; gap:8px; align-items:center; padding:8px 10px; border:1px solid rgba(255,255,255,0.12); border-radius:999px; background: rgba(255,255,255,0.04); margin:6px 6px 0 0;">
          <strong>${escapeHtml(k)}</strong>
          <span style="color:var(--muted);">${escapeHtml(v)}</span>
        </span>
      `;
    })
    .join("");

  return `<div>${pills}</div>`;
}

function renderGroundingRows(rows) {
  const data = rows || [];
  if (!data.length) {
    return `<p style="color:var(--muted); margin:0;">No grounding rows returned (check CSV loaded + test_code matching).</p>`;
  }

  // render as cards (more readable than a wide table)
  const cards = data
    .map((r) => {
      return `
        <div style="padding:12px; border:1px solid rgba(255,255,255,0.12); border-radius:12px; background: rgba(255,255,255,0.04); margin-top:10px;">
          <div style="display:flex; justify-content:space-between; gap:10px;">
            <div style="font-weight:800;">${escapeHtml(r.test_code)} — ${escapeHtml(r.test_name)}</div>
            <div style="color:var(--muted); font-size:12px;">Unit: ${escapeHtml(r.unit)}</div>
          </div>
          <div style="margin-top:8px; color:var(--muted); font-size:13px; line-height:1.5;">
            <div><strong style="color:var(--text);">Desirable:</strong> ${escapeHtml(r.desirable_range ?? "—")}</div>
            <div><strong style="color:var(--text);">Borderline:</strong> ${escapeHtml(r.borderline_high_range ?? "—")}</div>
            <div><strong style="color:var(--text);">High:</strong> ${escapeHtml(r.high_range ?? "—")}</div>
            ${r.low_range ? `<div><strong style="color:var(--text);">Low:</strong> ${escapeHtml(r.low_range)}</div>` : ""}
          </div>
          <div style="margin-top:10px; font-size:13px; line-height:1.6;">
            ${r.what_it_measures_plain ? `<div><strong>What it measures:</strong> ${escapeHtml(r.what_it_measures_plain)}</div>` : ""}
            ${r.how_to_read_results_plain ? `<div style="margin-top:6px;"><strong>How to read:</strong> ${escapeHtml(r.how_to_read_results_plain)}</div>` : ""}
            ${r.safe_next_step_plain ? `<div style="margin-top:6px;"><strong>Safe next step:</strong> ${escapeHtml(r.safe_next_step_plain)}</div>` : ""}
          </div>
        </div>
      `;
    })
    .join("");

  return `<div>${cards}</div>`;
}

function renderAiOverview(ai) {
  if (!ai) return `<p style="color:var(--muted); margin:0;">AI overview not available.</p>`;

  if (!ai.enabled) {
    return `
      <div style="padding:12px; border:1px solid rgba(255,255,255,0.12); border-radius:12px; background: rgba(255,255,255,0.04);">
        <div style="font-weight:700;">AI overview is OFF</div>
        <div style="margin-top:6px; color:var(--muted);">${escapeHtml(ai.message || "AI disabled")}</div>
        ${ai.error ? `<div style="margin-top:6px; color:var(--muted); font-size:12px;">error: ${escapeHtml(ai.error)}</div>` : ""}
      </div>
    `;
  }

  return `
    <div style="padding:12px; border:1px solid rgba(255,255,255,0.12); border-radius:12px; background: rgba(255,255,255,0.04);">
      <div style="display:flex; justify-content:space-between; gap:10px;">
        <div style="font-weight:800;">AI overview</div>
        <div style="color:var(--muted); font-size:12px;">${escapeHtml(ai.model || "")}</div>
      </div>
      <div style="margin-top:10px; white-space:pre-wrap; line-height:1.6;">${escapeHtml(ai.overview || "")}</div>
    </div>
  `;
}

function renderTextPreview(preview) {
  const p = preview || "";
  if (!p.trim()) return "";

  return `
    <details style="margin-top:12px;">
      <summary style="cursor:pointer; color:var(--muted);">show extracted text preview</summary>
      <pre style="white-space:pre-wrap; margin-top:10px; padding:12px; border:1px solid rgba(255,255,255,0.12); border-radius:12px; background: rgba(255,255,255,0.04); font-size:12px; line-height:1.5;">${escapeHtml(p)}</pre>
    </details>
  `;
}

function renderResults(payload) {
  const resultsEl = ensureResultsContainer();

  const detectedHtml = renderDetectedLipids(payload.detected_lipids);
  const groundingHtml = renderGroundingRows(payload.grounding_rows);
  const aiHtml = renderAiOverview(payload.ai_overview);
  const previewHtml = renderTextPreview(payload.text_preview);

  resultsEl.innerHTML = `
    <div style="margin-top:16px;">
      <h3 style="margin:0 0 10px 0;">results</h3>

      <div style="margin-top:12px;">
        <div style="font-weight:800; margin-bottom:8px;">detected lipids</div>
        ${detectedHtml}
      </div>

      <div style="margin-top:16px;">
        <div style="font-weight:800; margin-bottom:8px;">grounding reference</div>
        ${groundingHtml}
      </div>

      <div style="margin-top:16px;">
        ${aiHtml}
      </div>

      ${previewHtml}
    </div>
  `;
}

// ---- validation ----
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

// ---- events ----
fileInput.addEventListener("change", (e) => {
  const file = e.target.files?.[0];
  validateFile(file);
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const file = fileInput.files?.[0];
  if (!validateFile(file)) return;

  setError("");
  setLoading(true);

  try {
    const fd = new FormData();
    // IMPORTANT: backend expects parameter name "file"
    fd.append("file", file);

    const res = await fetch(UPLOAD_URL, {
      method: "POST",
      body: fd,
    });

    if (!res.ok) {
      let detail = "";
      try {
        const j = await res.json();
        detail = j?.detail ? (typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail)) : "";
      } catch (_) {}

      if (res.status === 413) {
        setError(detail || "file too large for server. increase MAX_MB in backend or upload smaller pdf.");
      } else if (res.status === 400) {
        setError(detail || "bad request. please upload a valid pdf.");
      } else if (res.status === 500) {
        setError(detail || "server error. check backend logs.");
      } else {
        setError(detail || `upload failed. status: ${res.status}`);
      }

      return;
    }

    const data = await res.json();
    renderResults(data);
  } catch (err) {
    setError("cannot reach backend. make sure uvicorn is running on http://127.0.0.1:8000 and CORS is enabled.");
  } finally {
    setLoading(false);
  }
});
