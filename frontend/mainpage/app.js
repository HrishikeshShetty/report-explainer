// pdf only + 20mb max (frontend validation)
const MAX_MB = 20;
const MAX_BYTES = MAX_MB * 1024 * 1024;

// report-overview backend
const API_BASE = "http://127.0.0.1:8000";
const UPLOAD_URL = `${API_BASE}/api/report-overview/upload`;

// chat backend (separate service)
const CHAT_API_BASE = "http://127.0.0.1:8001"; // change to 8000 only if chat is served on same port
const CHAT_URL = `${CHAT_API_BASE}/api/chat/ask`;
const HISTORY_URL = `${CHAT_API_BASE}/api/chat/history`;

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
let historyLoadedOnce = false;

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

  currentLipids = normalizeLipidsFromDetected(detected);
  currentReportId = payload?.report_id || payload?.reportId || null;

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

  const canChat = !!currentReportId || hasLipids();
  showChatSection(canChat);

  setUploadStatus("upload complete ✅");
  updateAskButtonState();

  scrollToEl(resultsSectionEl || chatSectionEl);
}

// ---- chat rendering ----
function renderChatResponse(data) {
  if (modePillEl) {
    if (data?.mode) {
      modePillEl.textContent = data.mode;
      modePillEl.classList.remove("hidden");
    } else {
      modePillEl.classList.add("hidden");
    }
  }

  if (noteTextEl) {
    if (data?.note) {
      noteTextEl.textContent = data.note;
      noteTextEl.classList.remove("hidden");
    } else {
      noteTextEl.classList.add("hidden");
    }
  }

  if (answerTextEl) {
    answerTextEl.textContent = data?.answer || "No answer returned.";
  }

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

// ---- UPDATED HISTORY RENDERING (newest on top + collapsible) ----
function renderHistory() {
  if (!chatHistoryEl || !historyItemsEl) return;

  if (!chatHistory.length) {
    chatHistoryEl.classList.add("hidden");
    historyItemsEl.innerHTML = "";
    return;
  }

  chatHistoryEl.classList.remove("hidden");
  historyItemsEl.innerHTML = "";

  const newestFirst = chatHistory.slice().reverse();

  newestFirst.forEach((item) => {
    const details = document.createElement("details");
    details.className = "history-item";

    const summary = document.createElement("summary");
    summary.textContent = item.q || "(no question)";
    details.appendChild(summary);

    const ans = document.createElement("div");
    ans.className = "history-answer";
    ans.innerHTML = `
      <div><b>A:</b> ${escapeHtml(item.a || "")}</div>
      ${item.mode ? `<div class="history-meta">mode: ${escapeHtml(item.mode)}</div>` : ""}
    `;
    details.appendChild(ans);

    historyItemsEl.appendChild(details);
  });
}

// ---- load history from backend (on refresh) ----
async function loadHistoryFromBackend() {
  if (historyLoadedOnce) return; // prevent double fetch
  historyLoadedOnce = true;

  try {
    const res = await fetch(`${HISTORY_URL}?limit=20&user_id=default`);
    if (!res.ok) return;

    const data = await res.json();
    const items = data?.items || [];
    if (!items.length) return;

    // reset local history to avoid duplicates
    chatHistory.length = 0;

    items.forEach((item) => {
      chatHistory.push({
        q: item.question,
        a: item.answer,
        mode: item.mode || "",
      });
    });

    renderHistory();
    showChatSection(true);
    updateAskButtonState();
  } catch (err) {
    console.warn("History load failed", err);
  }
}

// ---- events ----
if (fileInput) {
  fileInput.addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    validateFile(file);
  });
}

if (questionInputEl) {
  questionInputEl.addEventListener("input", () => {
    setChatError("");
    updateAskButtonState();
  });

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

    setError("");
    setUploadStatus("uploading…");
    setLoading(true);

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
      fd.append("file", file);

      const res = await fetch(UPLOAD_URL, { method: "POST", body: fd });

      if (!res.ok) {
        let detail = "";
        try {
          const j = await res.json();
          detail = j?.detail ? (typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail)) : "";
        } catch (_) {}

        if (res.status === 413) setError(detail || "file too large for server. upload a smaller pdf.");
        else if (res.status === 400) setError(detail || "bad request. please upload a valid pdf.");
        else if (res.status === 500) setError(detail || "server error. check backend logs.");
        else setError(detail || `upload failed. status: ${res.status}`);

        setUploadStatus("");
        return;
      }

      const data = await res.json();
      renderResults(data);

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

if (submitBtn) {
  submitBtn.addEventListener("click", () => {
    const evt = new Event("submit", { cancelable: true });
    form?.dispatchEvent(evt);
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
    const body = currentReportId
      ? { question, report_id: currentReportId, user_id: "default" }
      : { question, lipids: currentLipids, user_id: "default" };

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

    if (data?.report_id) {
      currentReportId = data.report_id;
      if (reportIdBadgeEl) {
        reportIdBadgeEl.textContent = `report_id: ${currentReportId}`;
        reportIdBadgeEl.classList.remove("hidden");
      }
    }

    renderChatResponse(data);

    // add to local history (newest will show on top)
    chatHistory.push({
      q: question,
      a: data?.answer || "",
      mode: data?.mode || "",
    });
    renderHistory();

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
  updateAskButtonState();
  askBtnEl.addEventListener("click", () => askQuestion());
}

// Initial state
showResultsSection(false);
showChatSection(false);
updateAskButtonState();

// load persisted history after refresh
loadHistoryFromBackend();
