from typing import Tuple


# Non-diagnostic guardrails and red flags to escalate
RED_FLAGS = [
    "seizure",
    "blue lips",
    "unconscious",
    "severe chest pain",
    "difficulty breathing",
    "trouble breathing",
    "not responsive",
    "stopped breathing",
    "choking",
    "head injury",
    "severe bleeding",
    "suicidal",
    "ingested poison",
    "allergic reaction",
]


CRISIS_MSG = (
    "This may be an emergency. I’m not a medical professional, but based on what you shared, "
    "please contact local emergency services immediately or your child’s clinician."
)


NON_DIAGNOSTIC_PREFACE = (
    "I can provide general, caregiver-friendly information about Down syndrome and IDD. "
    "I can’t diagnose, prescribe, or replace professional care."
)


def check_red_flags(text: str) -> Tuple[bool, str]:
    t = (text or "").lower()
    for rf in RED_FLAGS:
        if rf in t:
            return True, CRISIS_MSG
    return False, ""
