import os


class ChatEngine:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.mode = os.getenv("CHAT_MODE", "hybrid")

        # downgrade automatically if no key
        if not self.api_key:
            self.mode = "deterministic"

    def answer(self, question: str, lipids: dict):
        if self.mode == "deterministic":
            return self.rule_based_answer(question, lipids)

        # Future: AI mode
        return self.rule_based_answer(question, lipids)

    # ---------- RULE ENGINE ----------
    def rule_based_answer(self, question: str, lipids: dict):
        q = question.lower()

        if "ldl" in q:
            return self.ldl_logic(lipids.get("LDL"))

        if "hdl" in q:
            return self.hdl_logic(lipids.get("HDL"))

        if "triglyceride" in q or "tg" in q:
            return self.tg_logic(lipids.get("TG"))

        if "cholesterol" in q or "chol" in q:
            return self.chol_logic(lipids.get("CHOL"))

        return "Ask about LDL, HDL, triglycerides (TG), or total cholesterol."

    # ---------- INDIVIDUAL RULES ----------
    def ldl_logic(self, value):
        if value is None:
            return "LDL value not available."

        if value < 100:
            return "Your LDL is optimal."
        elif value < 130:
            return "Your LDL is near optimal."
        elif value < 160:
            return "Your LDL is borderline high."
        else:
            return "Your LDL is high."

    def hdl_logic(self, value):
        if value is None:
            return "HDL value not available."

        if value >= 60:
            return "Your HDL is protective (good)."
        elif value >= 40:
            return "Your HDL is acceptable."
        else:
            return "Your HDL is low."

    def tg_logic(self, value):
        if value is None:
            return "Triglyceride value not available."

        if value < 150:
            return "Your triglycerides are normal."
        elif value < 200:
            return "Your triglycerides are borderline high."
        else:
            return "Your triglycerides are high."

    def chol_logic(self, value):
        if value is None:
            return "Total cholesterol value not available."

        if value < 200:
            return "Your total cholesterol is desirable."
        elif value < 240:
            return "Your total cholesterol is borderline high."
        else:
            return "Your total cholesterol is high."