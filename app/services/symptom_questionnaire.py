"""Fixed, reviewable question list. The AI does not write questions in this stage."""
QUESTIONS = [
    ("main_reason", "What is the main reason you are seeking emergency care?"),
    ("symptoms", "What symptoms are you having?"),
    ("onset", "When did the symptoms begin?"),
    ("trend", "Are they staying the same, getting better, or getting worse?"),
    ("associated", "Any other symptoms along with these, such as fever, vomiting, dizziness, or pain elsewhere? (Say 'none' if not.)"),
    ("history", "Any medical conditions, allergies, or medicines we should know about? (Say 'none' if not.)"),
    ("other", "Is there anything else you think is important?"),
]
LABELS = {
    "main_reason": "Main reason", "symptoms": "Symptoms", "onset": "Started",
    "trend": "Changing", "associated": "Other symptoms", "history": "History, allergies, medicines",
    "other": "Other information",
}

def next_question(answered: int) -> str | None:
    return QUESTIONS[answered][1] if answered < len(QUESTIONS) else None

def labelled(answers: list[str]) -> str:
    return "\n".join(f"{LABELS[QUESTIONS[i][0]]}: {a}" for i, a in enumerate(answers[:len(QUESTIONS)]))
