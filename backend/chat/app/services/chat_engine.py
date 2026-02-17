import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def deterministic_answer(question: str, lipids: dict) -> str:
    if "ldl" in question.lower():
        ldl = lipids.get("LDL")
        if ldl:
            if ldl < 100:
                return "Your LDL is in the optimal range."
            elif ldl < 160:
                return "Your LDL is borderline high."
            else:
                return "Your LDL is high. Consider consulting a doctor."
    return "Ask about a specific lipid value like LDL, HDL, or TG."


def generate_chat_response(question: str, lipids: dict) -> str:
    if not OPENAI_API_KEY:
        return deterministic_answer(question, lipids)

    try:
        # future OpenAI integration
        return deterministic_answer(question, lipids)
    except Exception:
        return deterministic_answer(question, lipids)