import os
from pathlib import Path
from functools import lru_cache
from typing import Any, Dict, Optional

import pandas as pd


SUPPORTED_LIPIDS = {"CHOL", "LDL", "HDL", "TG"}


def _find_repo_root(start: Path) -> Path:
    """
    Robust repo root finder so paths work no matter where you run uvicorn from.
    Looks for a folder that contains: README.md + backend/
    """
    for p in [start] + list(start.parents):
        if (p / "README.md").exists() and (p / "backend").exists():
            return p
    # fallback (best-effort): go up to the repo root from this file location
    # chat_engine.py -> services -> app -> chat -> backend -> repo_root
    return start.parents[5]


REPO_ROOT = _find_repo_root(Path(__file__).resolve())

# reuse the existing grounding dataset from report-overview
CSV_PATH = (
    REPO_ROOT
    / "backend"
    / "report-overview"
    / "app"
    / "data"
    / "rag_lipid_reference_CHOL_LDL_HDL_TG.csv"
)


def _none_if_nan(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    return v


def _normalize_key(k: Any) -> str:
    if k is None:
        return ""
    s = str(k).strip().upper()
    if "TRIG" in s:
        return "TG"
    if s in {"TOTAL CHOLESTEROL", "CHOLESTEROL"}:
        return "CHOL"
    return s


def _detect_lipid_from_question(question: str) -> Optional[str]:
    q = (question or "").lower()
    if "ldl" in q:
        return "LDL"
    if "hdl" in q:
        return "HDL"
    if "trig" in q or "tg" in q:
        return "TG"
    if "chol" in q or "total cholesterol" in q:
        return "CHOL"
    return None


@lru_cache(maxsize=1)
def _load_reference_df() -> pd.DataFrame:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Reference CSV not found at: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip() for c in df.columns]

    # normalize test_code for stable matching
    if "test_code" in df.columns:
        df["test_code"] = df["test_code"].astype(str).str.strip().str.upper()

    return df


def _get_row(df: pd.DataFrame, code: str) -> Dict[str, Any]:
    match = df[df["test_code"] == code]
    if match.empty:
        raise ValueError(f"No row found in reference CSV for test_code={code}")
    row = match.iloc[0].to_dict()

    # make row JSON-safe (no NaN)
    return {k: _none_if_nan(v) for k, v in row.items()}


def _safe_text(row: Dict[str, Any], key: str) -> str:
    v = row.get(key)
    if v is None:
        return ""
    return str(v).strip()


def _build_ranges(row: Dict[str, Any]) -> Dict[str, Any]:
    # IMPORTANT: convert NaN -> None to avoid "Out of range float values are not JSON compliant"
    return {
        "desirable_range": _none_if_nan(row.get("desirable_range")),
        "borderline_high_range": _none_if_nan(row.get("borderline_high_range")),
        "high_range": _none_if_nan(row.get("high_range")),
        "low_range": _none_if_nan(row.get("low_range")),
        "sex_specific_ranges": _none_if_nan(row.get("sex_specific_ranges")),
    }


class ChatEngine:
    """
    Deterministic-first chat engine.

    - If OPENAI_API_KEY is missing => deterministic mode
    - If present => hybrid mode (future AI integration), still safe fallback
    """

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.mode = os.getenv("CHAT_MODE", "hybrid").strip().lower()

        if not self.api_key:
            self.mode = "deterministic"

        # Try to load grounding CSV; if missing, degrade gracefully (still works with cutoffs)
        try:
            self.df = _load_reference_df()
        except FileNotFoundError:
            self.df = None

    def _mode_note(self) -> Optional[str]:
        # clear, explicit behavior (so your repo is "ready" without keys)
        if self.mode == "deterministic":
            return "OPENAI_API_KEY not set, running in deterministic mode."
        return None

    def answer(self, question: str, lipids: dict) -> Dict[str, Any]:
        # deterministic now (AI integration later)
        return self.grounded_answer(question, lipids)

    def grounded_answer(self, question: str, lipids: dict) -> Dict[str, Any]:
        asked = _detect_lipid_from_question(question)

        # normalize & keep only supported lipids
        clean: Dict[str, float] = {}
        for k, v in (lipids or {}).items():
            kk = _normalize_key(k)
            if kk in SUPPORTED_LIPIDS:
                try:
                    clean[kk] = float(v)
                except Exception:
                    pass

        if not clean:
            return {
                "answer": "I couldn’t find valid lipid values (CHOL, LDL, HDL, TG) in your request.",
                "details": [],
                "highlights": [],
                "sources": [],
                "mode": "deterministic" if self.mode == "deterministic" else "hybrid",
                "note": self._mode_note(),
            }

        # focus one lipid if asked, else summarize all provided
        lipids_to_process = [asked] if asked in clean else list(clean.keys())

        details = []
        highlights = []
        sources = []

        for code in lipids_to_process:
            value = clean[code]

            row: Dict[str, Any] = {}
            if self.df is not None:
                row = _get_row(self.df, code)

            unit = _safe_text(row, "unit") or "mg/dL"
            ranges = (
                _build_ranges(row)
                if row
                else {
                    "desirable_range": None,
                    "borderline_high_range": None,
                    "high_range": None,
                    "low_range": None,
                    "sex_specific_ranges": None,
                }
            )

            category = self._category(code, value)

            what = _safe_text(row, "what_it_measures_plain")
            how = _safe_text(row, "how_to_read_results_plain")
            hi = _safe_text(row, "if_high_may_mean_plain")
            lo = _safe_text(row, "if_low_may_mean_plain")
            next_step = _safe_text(row, "safe_next_step_plain")

            details.append(
                {
                    "lipid": code,
                    "test_name": _safe_text(row, "test_name") if row else "",
                    "value": value,
                    "unit": unit,
                    "category": category,
                    "ranges": ranges,  # JSON-safe (no NaN)
                    "grounding": {
                        "what_it_measures_plain": what,
                        "how_to_read_results_plain": how,
                        "if_high_may_mean_plain": hi,
                        "if_low_may_mean_plain": lo,
                        "safe_next_step_plain": next_step,
                    },
                }
            )

            if row:
                sources.append(f"rag_lipid_reference_CHOL_LDL_HDL_TG.csv:{code}")

            if category in {"borderline-high", "high", "very-high", "low"}:
                msg = f"{code} looks {category.replace('-', ' ')}."
                if msg not in highlights:
                    highlights.append(msg)

        # build answer text
        if asked and asked in clean:
            d = details[0]
            parts = [
                f"Your {d['lipid']} is {d['category'].replace('-', ' ')}.",
                d["grounding"].get("what_it_measures_plain", ""),
                d["grounding"].get("how_to_read_results_plain", ""),
                d["grounding"].get("safe_next_step_plain", ""),
            ]
            answer = " ".join([p.strip() for p in parts if p and p.strip()])
        else:
            if highlights:
                answer = "Here’s a quick summary of your lipid values. " + " ".join(highlights)
            else:
                answer = "Here’s a quick summary of your lipid values. Nothing stands out as clearly abnormal based on standard cutoffs."

        answer = (answer + " This is general information, not medical advice.").strip()

        return {
            "answer": answer,
            "details": details,
            "highlights": highlights,
            "sources": sources,
            "mode": "deterministic" if self.mode == "deterministic" else "hybrid",
            "note": self._mode_note(),
        }

    # ---------- Deterministic categorization ----------
    def _category(self, code: str, value: float) -> str:
        """
        Deterministic categorization using standard thresholds.
        (We still *display* ranges from the CSV, but we don't parse them.)
        """
        if code == "CHOL":
            if value < 200:
                return "desirable"
            if value < 240:
                return "borderline-high"
            return "high"

        if code == "LDL":
            if value < 100:
                return "optimal"
            if value < 130:
                return "near-optimal"
            if value < 160:
                return "borderline-high"
            if value < 190:
                return "high"
            return "very-high"

        if code == "HDL":
            if value < 40:
                return "low"
            if value >= 60:
                return "protective"
            return "acceptable"

        if code == "TG":
            if value < 150:
                return "normal"
            if value < 200:
                return "borderline-high"
            if value < 500:
                return "high"
            return "very-high"

        return "unknown"
