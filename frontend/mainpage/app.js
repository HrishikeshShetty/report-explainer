// pdf only + 20mb max (frontend validation)
const MAX_MB = 20;
const MAX_BYTES = MAX_MB * 1024 * 1024;

// report-overview backend
const API_BASE = "http://127.0.0.1:8000";
const UPLOAD_URL = `${API_BASE}/api/report-overview/upload`;

// chat backend (separate service)
const CHAT_API_BASE = "http://127.0.0.1:8001"; // change to 8000 only if chat is served on same port
const CHAT_URL = `${CHAT_API_BASE}/api/chat/ask`;

// ---- DOM ----
const fileInput = document.getElementById("pdfFile");
const errorBox = document.getElementById("errorBox");
const submitBtn = document.getElementById("submitBtn");
const form = document.getElementById("uploadForm");

// Upload / Results
const uploadStatusEl = document.getElementById("uploadStatus");
const resultsSectionEl = document.getElementById("resultsSection");
const lipidsTableBodyEl = document.getElementById("lipidsTableBody");
const reportIdBadgeEl = document.getElementById("reportIdBadge");
const extractionBadgeEl = document.getElementById("extractionBadge");

// Chat
const chatSectionEl = document.getElementById("chatSection");
const chatErrorBoxEl = document.getElementById("chatErrorBox");
const questionInputEl = document.getElementById("questionInput");
const askBtnEl = document.getElementById("askBtn");
const chatLoadingEl = document.getElementById("chatLoading");
const chatResponseEl = document.getElementById("chatResponse");

const answerTextEl = document.getElementById("answerText");
const modePillEl = document.getElementById("modePill");
const noteTextEl = document.getElementById("noteText");
const highlightsListEl = document.getElementById("highlightsList");
const sourcesDetailsEl = document.getElementById("sourcesDetails");
const sourcesListEl = document.getElementById("sourcesList");

// History (client-side)
const chatHistoryEl = document.getElementById("chatHistory");
const historyItemsEl = document.getElementById("historyItems");

// ---- client state ----
let currentLipids = null;   // { CHOL, LDL, HDL, TG }
let currentReportId = null; // uuid (optional)
const chatHistory = [];     // [{q,a,mode}]

// ---- utilities ----
function escapeHtml(str) {
  return String(str ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function scrollToEl(el) {
  try {
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (_) {}
}

function setError(message) {
  if (!errorBox) return;
  errorBox.textContent = message || "";
}

function setUploadStatus(message) {
  if (!uploadStatusEl) return;
  uploadStatusEl.textContent = message || "";
}

function setLoading(isLoading) {
  if (!submitBtn) return;
  submitBtn.disabled = isLoading;
  submitBtn.textContent = isLoading ? "uploading..." : "continue";
}

function showResultsSection(show) {
  if (!resultsSectionEl) return;
  resultsSectionEl.classList.toggle("hidden", !show);
}

function showChatSection(show) {
  if (!chatSectionEl) return;
  chatSectionEl.classList.toggle("hidden", !show);
}

function setChatError(message) {
  if (!chatErrorBoxEl) return;
  chatErrorBoxEl.textContent = message || "";
}

function setChatLoading(isLoading) {
  if (chatLoadingEl) chatLoadingEl.classList.toggle("hidden", !isLoading);
  if (askBtnEl) askBtnEl.disabled = isLoading || !canAskNow();
}

function showChatResponse(show) {
  if (!chatResponseEl) return;
  chatResponseEl.classList.toggle("hidden", !show);
}

function hasLipids() {
  return !!currentLipids && Object.keys(currentLipids).length > 0;
}

function canAskNow() {
  const q = (questionInputEl?.value || "").trim();
  return !!q && (hasLipids() || !!currentReportId);
}

function updateAskButtonState() {
  if (!askBtnEl) return;
  askBtnEl.disabled = !canAskNow();
}

// ---- validation ----
function validateFile(file) {
  if (!file) {
    setError("please select a pdf file.");
    if (submitBtn) submitBtn.disabled = true;
    return false;
  }

  const isPdfMime = file.type === "application/pdf";
  const isPdfExt = file.name.toLowerCase().endsWith(".pdf");

  if (!isPdfMime && !isPdfExt) {
    setError("only pdf files are allowed.");
    if (submitBtn) submitBtn.disabled = true;
    return false;
  }

  if (file.size > MAX_BYTES) {
    setError(`file is too large. max allowed is ${MAX_MB}mb.`);
    if (submitBtn) submitBtn.disabled = true;
    return false;
  }

  setError("");
  if (submitBtn) submitBtn.disabled = false;
  return true;
}

// ---- lipids helpers ----
function normalizeLipidsFromDetected(detected) {
  const out = {};
  if (!detected || typeof detected !== "object") return out;

  for (const key of ["CHOL", "LDL", "HDL", "TG"]) {
    const v = detected[key];
    if (v !== undefined && v !== null && String(v).trim() !== "") out[key] = v;
  }
  return out;
}

function renderLipidsTable(lipidsObj, groundingRows) {
  if (!lipidsTableBodyEl) return;

  const rowsByCode = new Map();
  (groundingRows || []).forEach((r) => {
    if (r?.test_code) rowsByCode.set(String(r.test_code).toUpperCase(), r);
  });

  const keys = ["CHOL", "LDL", "HDL", "TG"];

  const html = keys
    .map((k) => {
      const v = lipidsObj?.[k];
      const row = rowsByCode.get(k);

      let displayValue = v ?? "—";
      if (typeof v === "object" && v !== null) {
        displayValue = v.value ?? JSON.stringify(v);
      }

      const unit = row?.unit ?? (typeof v === "object" && v ? (v.unit ?? "—") : "—");

      const range =
        row?.desirable_range ??
        row?.optimal_range ??
        row?.reference_range ??
        row?.normal_range ??
        "—";

      return `
        <tr>
          <td>${escapeHtml(k)}</td>
          <td>${escapeHtml(displayValue)}</td>
          <td>${escapeHtml(unit)}</td>
          <td>${escapeHtml(range)}</td>
        </tr>
      `;
    })
    .join("");

  lipidsTableBodyEl.innerHTML = html;
}

function renderResults(payload) {
  const detected = payload?.detected_lipids || {};
  const groundingRows = payload?.grounding_rows || [];

  // store state
  currentLipids = normalizeLipidsFromDetected(detected);

  // report-overview may or may not return report_id
  currentReportId = payload?.report_id || payload?.reportId || null;

  // badges
  if (reportIdBadgeEl) {
    if (currentReportId) {
      reportIdBadgeEl.textContent = `report_id: ${currentReportId}`;
      reportIdBadgeEl.classList.remove("hidden");
    } else {
      reportIdBadgeEl.classList.add("hidden");
    }
  }

  if (extractionBadgeEl) {
    const foundCount = Object.keys(currentLipids).length;
    extractionBadgeEl.textContent = `detected: ${foundCount}/4`;
    extractionBadgeEl.classList.remove("hidden");
  }

  renderLipidsTable(currentLipids, groundingRows);
  showResultsSection(true);

  // enable chat if we have lipids or report id
  const canChat = !!currentReportId || hasLipids();
  showChatSection(canChat);

  setUploadStatus("upload complete ✅");

  // now that we have state, update Ask button
  updateAskButtonState();

  // smooth scroll to results (nice UX)
  scrollToEl(resultsSectionEl || chatSectionEl);
}

// ---- chat rendering ----
function renderChatResponse(data) {
  // mode pill
  if (modePillEl) {
    if (data?.mode) {
      modePillEl.textContent = data.mode;
      modePillEl.classList.remove("hidden");
    } else {
      modePillEl.classList.add("hidden");
    }
  }

  // note
  if (noteTextEl) {
    if (data?.note) {
      noteTextEl.textContent = data.note;
      noteTextEl.classList.remove("hidden");
    } else {
      noteTextEl.classList.add("hidden");
    }
  }

  // answer
  if (answerTextEl) {
    answerTextEl.textContent = data?.answer || "No answer returned.";
  }

  // highlights
  if (highlightsListEl) {
    const highlights = Array.isArray(data?.highlights) ? data.highlights : [];
    if (highlights.length) {
      highlightsListEl.innerHTML = highlights.map((h) => `<li>${escapeHtml(h)}</li>`).join("");
      highlightsListEl.classList.remove("hidden");
    } else {
      highlightsListEl.innerHTML = "";
      highlightsListEl.classList.add("hidden");
    }
  }

  // sources
  if (sourcesDetailsEl && sourcesListEl) {
    const sources = Array.isArray(data?.sources) ? data.sources : [];
    if (sources.length) {
      sourcesListEl.innerHTML = sources.map((s) => `<li>${escapeHtml(s)}</li>`).join("");
      sourcesDetailsEl.classList.remove("hidden");
    } else {
      sourcesListEl.innerHTML = "";
      sourcesDetailsEl.classList.add("hidden");
    }
  }

  showChatResponse(true);
  scrollToEl(chatResponseEl);
}

function renderHistory() {
  if (!chatHistoryEl || !historyItemsEl) return;

  if (!chatHistory.length) {
    chatHistoryEl.classList.add("hidden");
    historyItemsEl.innerHTML = "";
    return;
  }

  chatHistoryEl.classList.remove("hidden");

  historyItemsEl.innerHTML = chatHistory
    .slice()
    .reverse()
    .map((item) => {
      return `
        <div style="margin-top:10px; padding:10px; border:1px solid rgba(255,255,255,0.12); border-radius:12px; background: rgba(255,255,255,0.04);">
          <div style="font-weight:800;">Q:</div>
          <div style="color:var(--muted); margin-top:4px;">${escapeHtml(item.q)}</div>
          <div style="font-weight:800; margin-top:8px;">A:</div>
          <div style="margin-top:4px; line-height:1.7;">${escapeHtml(item.a)}</div>
          ${item.mode ? `<div style="margin-top:8px; color:var(--muted); font-size:12px;">mode: ${escapeHtml(item.mode)}</div>` : ""}
        </div>
      `;
    })
    .join("");

  scrollToEl(chatHistoryEl);
}

// ---- events ----
if (fileInput) {
  fileInput.addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    validateFile(file);
  });
}

// enable/disable Ask as user types
if (questionInputEl) {
  questionInputEl.addEventListener("input", () => {
    setChatError("");
    updateAskButtonState();
  });

  // Enter to send (Shift+Enter = newline)
  questionInputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!askBtnEl?.disabled) askBtnEl.click();
    }
  });
}

if (form) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const file = fileInput?.files?.[0];
    if (!validateFile(file)) return;

    // reset UI bits
    setError("");
    setUploadStatus("uploading…");
    setLoading(true);

    // reset state for clean re-upload
    currentLipids = null;
    currentReportId = null;
    showResultsSection(false);
    showChatSection(false);
    setChatError("");
    showChatResponse(false);
    if (reportIdBadgeEl) reportIdBadgeEl.classList.add("hidden");
    if (extractionBadgeEl) extractionBadgeEl.classList.add("hidden");
    updateAskButtonState();

    try {
      const fd = new FormData();
      fd.append("file", file); // backend expects "file"

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
          setError(detail || "file too large for server. upload a smaller pdf.");
        } else if (res.status === 400) {
          setError(detail || "bad request. please upload a valid pdf.");
        } else if (res.status === 500) {
          setError(detail || "server error. check backend logs.");
        } else {
          setError(detail || `upload failed. status: ${res.status}`);
        }

        setUploadStatus("");
        return;
      }

      const data = await res.json();
      renderResults(data);

      // If chat is now available, focus the question box
      if (!chatSectionEl?.classList.contains("hidden")) {
        questionInputEl?.focus();
      }
    } catch (err) {
      setError("cannot reach backend. make sure report-overview is running on http://127.0.0.1:8000 and CORS is enabled.");
      setUploadStatus("");
    } finally {
      setLoading(false);
    }
  });
}

// Chat ask
async function askQuestion() {
  const question = (questionInputEl?.value || "").trim();
  if (!question) {
    setChatError("please enter a question.");
    updateAskButtonState();
    return;
  }

  if (!currentReportId && !hasLipids()) {
    setChatError("please upload a report first (no lipid values available yet).");
    updateAskButtonState();
    return;
  }

  setChatError("");
  setChatLoading(true);
  showChatResponse(false);

  try {
    // prefer report_id; fallback to sending lipids
    const body = currentReportId
      ? { question, report_id: currentReportId }
      : { question, lipids: currentLipids };

    const res = await fetch(CHAT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      let detail = "";
      try {
        const j = await res.json();
        detail = j?.detail ? (typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail)) : "";
      } catch (_) {}

      setChatError(detail || `chat failed. status: ${res.status}`);
      return;
    }

    const data = await res.json();

    // if chat returns report_id, store it for follow-ups
    if (data?.report_id) {
      currentReportId = data.report_id;

      if (reportIdBadgeEl) {
        reportIdBadgeEl.textContent = `report_id: ${currentReportId}`;
        reportIdBadgeEl.classList.remove("hidden");
      }
    }

    renderChatResponse(data);

    // client history
    chatHistory.push({
      q: question,
      a: data?.answer || "",
      mode: data?.mode || "",
    });
    renderHistory();

    // clear input after sending
    if (questionInputEl) questionInputEl.value = "";
    updateAskButtonState();
    questionInputEl?.focus();
  } catch (err) {
    setChatError("cannot reach chat backend. make sure chat service is running on http://127.0.0.1:8001 and CORS is enabled.");
  } finally {
    setChatLoading(false);
  }
}

if (askBtnEl) {
  // start disabled until upload + input text
  updateAskButtonState();

  askBtnEl.addEventListener("click", () => {
    askQuestion();
  });
}

// Initial state
showResultsSection(false);
showChatSection(false);
updateAskButtonState();
