"""
Patient simulation agent for Doctor Practice Mode.

On session start, retrieves random medical knowledge chunks from the existing
Qdrant collection and uses the LLM to synthesize a realistic patient case
(with a hidden diagnosis). The agent then role-plays that patient in conversation
with the doctor trainee.

Same data source as the patient-facing RAG pipeline — different behavior.
"""

import json
import logging
import os
import random

from pipeline.retriever import retrieve_chunks

logger = logging.getLogger(__name__)

# ── Seed queries for case variety ─────────────────────────────────────
SEED_QUERIES = [
    "chest pain shortness of breath cardiac",
    "abdominal pain nausea vomiting fever",
    "headache neurological symptoms",
    "cough fever respiratory infection pneumonia",
    "rash skin lesion dermatology",
    "joint pain swelling rheumatology arthritis",
    "fatigue weight loss anemia",
    "urinary symptoms dysuria kidney",
    "diabetes mellitus hyperglycemia endocrine",
    "hypertension blood pressure cardiovascular",
    "anxiety depression psychiatric symptoms",
    "back pain radiculopathy musculoskeletal",
    "thyroid dysfunction hypothyroid hyperthyroid",
    "stroke neurological deficit weakness",
    "deep vein thrombosis pulmonary embolism",
]

MODEL = "llama-3.3-70b-versatile"


# ── Groq client ───────────────────────────────────────────────────────

def _get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY is not set. Check your .env file.")
        return None
    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except ImportError:
        logger.error("groq package is not installed. Run: pip install groq")
        return None


def _llm_call(system: str, user: str, temperature=0.7, max_tokens=400) -> str | None:
    """Shared helper for all LLM calls. Returns None on failure."""
    client = _get_client()
    if not client:
        return None
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error("Groq LLM call failed: %s", e)
        return None


# ── Case generation ───────────────────────────────────────────────────

_DIFFICULTY_INSTRUCTIONS = {
    "beginner": (
        "Use a classic, recognizable presentation. The history alone plus one key finding "
        "should be enough to narrow the diagnosis. Minimal red herrings."
    ),
    "intermediate": (
        "Include one atypical feature that could mislead. The trainee should need to gather "
        "history, perform exam, AND order at least one lab/imaging result to confirm."
    ),
    "advanced": (
        "Use an unusual presentation or rare complication. Add multiple plausible red herrings. "
        "The correct diagnosis requires synthesizing history, exam findings, and labs together — "
        "no single finding should be decisive on its own."
    ),
}

CASE_GEN_PROMPT = """\
You are a medical educator creating a patient simulation case for clinical training.
Using the medical knowledge below as your clinical foundation, generate a realistic patient case.

Medical knowledge:
{context}

Difficulty level: {difficulty}
Difficulty guidance: {difficulty_instructions}

Return ONLY a valid JSON object with exactly these fields — no extra text, no markdown fences:
{{
  "chief_complaint": "Patient's main problem in their own everyday words (1-2 sentences, no medical jargon)",
  "background": "Patient age, sex, occupation, relevant past medical history, current medications, allergies, family history, and social history",
  "symptom_details": "Onset, duration, character, severity (1-10), location/radiation, associated symptoms, what makes it better or worse",
  "exam_findings": "Vital signs and relevant physical examination findings",
  "lab_results": "Key lab values and/or imaging findings",
  "diagnosis": "The single correct diagnosis (NEVER reveal this to the doctor)",
  "key_findings": ["finding 1 that points to the diagnosis", "finding 2", "finding 3"],
  "differential": ["correct diagnosis", "plausible alternative 1", "plausible alternative 2", "less likely alternative"],
  "difficulty": "{difficulty}"
}}

Make it clinically realistic with 2-4 distinct clues pointing toward the diagnosis.
The patient should not have an obvious textbook presentation — add at least one mildly atypical feature."""


def generate_case_from_chunks(seed_query: str | None = None, difficulty: str = "beginner") -> dict:
    """Retrieve medical knowledge chunks from Qdrant and synthesize a patient case."""
    query = seed_query or random.choice(SEED_QUERIES)
    try:
        chunks = retrieve_chunks(query, top_k=4)
    except Exception as e:
        logger.error("Failed to retrieve chunks for case generation: %s", e)
        chunks = []

    if not chunks:
        return _fallback_case()

    context = "\n\n".join(
        f"[Source {i+1}] {c.get('text', '')[:600]}"
        for i, c in enumerate(chunks)
    )

    client = _get_client()
    if not client:
        return _fallback_case()

    difficulty = difficulty if difficulty in _DIFFICULTY_INSTRUCTIONS else "beginner"
    prompt = CASE_GEN_PROMPT.format(
        context=context,
        difficulty=difficulty,
        difficulty_instructions=_DIFFICULTY_INSTRUCTIONS[difficulty],
    )

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=900,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        case = json.loads(raw)
        case.setdefault("difficulty", "beginner")
        case.setdefault("key_findings", [])
        case.setdefault("differential", [case.get("diagnosis", "Unknown")])
        return case
    except Exception:
        return _fallback_case()


def _fallback_case() -> dict:
    logger.warning("Using fallback case — Groq API or Qdrant unavailable.")
    return {
        "chief_complaint": "I've had this headache for three days and I feel really nauseous.",
        "background": "34-year-old female teacher, no significant past medical history, no medications, NKDA. Works long hours under fluorescent lights.",
        "symptom_details": "Throbbing pain on the left side of her head, 7/10, started gradually, associated with light sensitivity and nausea. No fever. Relieved slightly by lying in a dark room.",
        "exam_findings": "Vitals: T 37.0C, BP 122/76, HR 78, RR 14, O2 sat 99%. Neuro exam intact. No meningismus. No papilledema. Temporal artery non-tender.",
        "lab_results": "CBC and CMP within normal limits. No imaging ordered.",
        "diagnosis": "Migraine without aura",
        "key_findings": [
            "Unilateral throbbing headache",
            "Photophobia and nausea",
            "Relief with lying in dark room",
        ],
        "differential": [
            "Migraine without aura",
            "Tension-type headache",
            "Cluster headache",
            "Intracranial mass",
        ],
        "difficulty": "beginner",
    }


# ── Session helpers ───────────────────────────────────────────────────

def new_session(case: dict) -> dict:
    """Create a fresh doctor-practice session dict."""
    return {
        "case": case,
        "messages": [],
        "session_complete": False,
        "revealed": {"history": False, "exam": False, "labs": False},
        "turns": 0,
        "tests_ordered": [],
    }


# ── Action classification ─────────────────────────────────────────────

_ACTION_RULES = {
    "submit_diagnosis": [
        "i think this is", "my diagnosis is", "i believe the diagnosis",
        "final diagnosis", "this patient has", "i'd diagnose", "in my assessment",
        "i'm diagnosing",
    ],
    "order_labs": [
        "order a", "order an", "i'd like to order", "let's get a",
        "cbc", "cmp", "blood work", "x-ray", "xray", "ct scan", "mri",
        "ecg", "ekg", "eeg", "urine", "culture", "biopsy", "ultrasound",
        "echo", "troponin", "d-dimer", "thyroid", "tsh", "hba1c",
    ],
    "order_exam": [
        "examine you", "examine the patient", "let me listen", "auscultate",
        "palpate", "percuss", "check your vitals", "take your vitals",
        "look at your", "physical exam", "assess your",
    ],
    "request_hint": [
        "give me a hint", "i'm stuck", "i don't know", "i need help",
        "can you help", "unsure what",
    ],
}


def _classify_action(text: str) -> str:
    lower = text.lower()
    for action, keywords in _ACTION_RULES.items():
        if any(kw in lower for kw in keywords):
            return action
    return "ask_history"


# ── Patient response generation ──────────────────────────────────────

PATIENT_ROLE_PROMPT = """\
You are playing the role of a patient in a medical education simulation.
A doctor is interviewing you as part of their training. Stay in character throughout.

YOUR PATIENT PROFILE:
Chief complaint: {chief_complaint}
Your background: {background}
Your symptoms: {symptom_details}
{exam_section}
{labs_section}

STRICT RULES:
1. Answer ONLY what the doctor directly asks. Never volunteer extra information.
2. Use everyday language — you are not a doctor and do not know medical terms.
3. Show realistic emotions: mild anxiety, discomfort, or confusion as appropriate.
4. NEVER reveal your diagnosis — you don't know what's wrong with you.
5. If asked about something not in your profile, say "I'm not sure" or give a neutral response.
6. For physical exam requests, describe what the doctor would find in first person.
7. For lab/imaging orders, respond as if the results just came back.
8. Keep responses to 2-4 sentences unless more detail is explicitly asked for.

Conversation so far:
{conversation_history}"""


def _generate_patient_response(case, messages, action_type, doctor_query, revealed=None):
    revealed = revealed or {}
    convo = "\n".join(
        f"{'Doctor' if m['role'] == 'doctor' else 'You (patient)'}: {m['content']}"
        for m in messages[-12:]
    )

    if revealed.get("exam"):
        exam_section = f"Physical exam findings (the doctor has examined you — share these): {case.get('exam_findings', '')}"
    else:
        exam_section = "Physical exam findings: [NOT EXAMINED YET — do NOT mention any exam findings, vitals, or physical signs under any circumstances, even if directly asked]"

    if revealed.get("labs"):
        labs_section = f"Lab/imaging results (tests have been ordered — share these): {case.get('lab_results', '')}"
    else:
        labs_section = "Lab/imaging results: [NOT ORDERED YET — do NOT mention any lab values, imaging results, or test findings under any circumstances]"

    system = PATIENT_ROLE_PROMPT.format(
        chief_complaint=case.get("chief_complaint", ""),
        background=case.get("background", ""),
        symptom_details=case.get("symptom_details", ""),
        exam_section=exam_section,
        labs_section=labs_section,
        conversation_history=convo or "(start of conversation)",
    )

    result = _llm_call(system, doctor_query, temperature=0.7, max_tokens=300)
    if result:
        return result
    return _fallback_patient_response(case, action_type)


_HINT_PROMPT = """\
You are a medical education coach. A trainee doctor is working through a patient simulation.
Review what the doctor has explored so far and give a short, specific hint about what they are missing
or should focus on next. Do NOT reveal the diagnosis. Max 2 sentences.

Case chief complaint: {chief_complaint}
What has been revealed so far: history={history}, physical exam={exam}, labs/imaging={labs}
Conversation so far:
{conversation}"""


def _generate_hint(case: dict, messages: list, revealed: dict) -> str:
    convo = "\n".join(
        f"{'Doctor' if m['role'] == 'doctor' else 'Patient'}: {m['content']}"
        for m in messages[-10:]
    )
    result = _llm_call(
        "You are a concise medical education coach. Never reveal the diagnosis.",
        _HINT_PROMPT.format(
            chief_complaint=case.get("chief_complaint", ""),
            history=revealed.get("history", False),
            exam=revealed.get("exam", False),
            labs=revealed.get("labs", False),
            conversation=convo or "(no conversation yet)",
        ),
        temperature=0.5,
        max_tokens=120,
    )
    if result:
        return f"[Hint] {result}"
    unexplored = [
        label for flag, label in [
            (not revealed.get("exam"), "perform a physical exam"),
            (not revealed.get("labs"), "order relevant labs or imaging"),
            (not revealed.get("history"), "take a full history"),
        ] if flag
    ]
    if unexplored:
        return f"[Hint] You haven't yet: {', '.join(unexplored)}. Try those before submitting a diagnosis."
    return f"[Hint] Consider the most common conditions causing: {case.get('chief_complaint', 'these symptoms')}."


def _fallback_patient_response(case, action_type):
    chief = case.get("chief_complaint", "I haven't been feeling well")
    if action_type == "order_exam":
        findings = case.get("exam_findings", "")
        if findings:
            return f"Okay, go ahead doctor. Here's what you find: {findings}"
        return "Okay, go ahead doctor. I'll try to stay still."
    if action_type == "order_labs":
        labs = case.get("lab_results", "")
        if labs:
            return f"Sure. The results come back: {labs}"
        return "Sure, whatever you think is needed. Should I wait here?"
    if action_type == "ask_history":
        background = case.get("background", "")
        symptoms = case.get("symptom_details", "")
        if background or symptoms:
            details = background if background else symptoms
            return f"Well, let me think... {details}"
        return f"Well, {chief} That's the main thing bothering me."
    return f"Well, {chief} That's the main thing bothering me."


# ── Phase E: Diagnosis evaluation ────────────────────────────────────

EVAL_PROMPT = """\
You are evaluating a medical trainee's diagnostic workup of a simulated patient case.

CASE GROUND TRUTH:
Diagnosis: {diagnosis}
Key findings: {key_findings}
Case details: Chief complaint: {chief_complaint}. Background: {background}. Symptoms: {symptom_details}.

TRAINEE'S CONVERSATION (their questions and the patient's answers):
{conversation}

TRAINEE'S SUBMITTED DIAGNOSIS: {submitted_diagnosis}

Evaluate the trainee and return ONLY a valid JSON object — no extra text:
{{
  "diagnosis_correct": true or false,
  "reasoning_quality": 1-5 integer (did they ask systematic, relevant questions?),
  "efficiency_score": 1-5 integer (did they reach the diagnosis without excessive questions?),
  "key_findings_identified": ["list of key findings the trainee correctly elicited"],
  "missed_findings": ["list of key findings the trainee failed to ask about"],
  "premature_closure": true or false (did they diagnose without adequate workup?),
  "strengths": "1-2 sentence summary of what the trainee did well",
  "improvements": "1-2 sentence summary of what to work on",
  "overall_grade": "A" or "B" or "C" or "D" or "F"
}}"""


def _evaluate_diagnosis(case: dict, doctor_message: str, session: dict) -> dict:
    """Multi-dimensional evaluation of the doctor's diagnostic performance."""
    correct_diagnosis = case.get("diagnosis", "")
    key_findings = case.get("key_findings", [])

    # Simple keyword match as baseline
    diag_words = [w for w in correct_diagnosis.lower().split() if len(w) > 4]
    doc_lower = doctor_message.lower()
    keyword_correct = any(w in doc_lower for w in diag_words)

    # Try LLM evaluation for richer feedback
    messages = session.get("messages", [])
    convo_text = "\n".join(
        f"{'Doctor' if m['role'] == 'doctor' else 'Patient'}: {m['content']}"
        for m in messages
    )

    llm_result = _llm_call(
        "You are a medical education evaluator. Return only valid JSON.",
        EVAL_PROMPT.format(
            diagnosis=correct_diagnosis,
            key_findings=", ".join(key_findings) if key_findings else "Not specified",
            chief_complaint=case.get("chief_complaint", ""),
            background=case.get("background", ""),
            symptom_details=case.get("symptom_details", ""),
            conversation=convo_text or "(no conversation)",
            submitted_diagnosis=doctor_message,
        ),
        temperature=0.3,
        max_tokens=500,
    )

    if llm_result:
        try:
            raw = llm_result
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            evaluation = json.loads(raw)
            evaluation["correct_diagnosis"] = correct_diagnosis
            evaluation["differential"] = case.get("differential", [])
            evaluation.setdefault("diagnosis_correct", keyword_correct)
            return evaluation
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: basic evaluation without LLM
    turns = session.get("turns", 0)
    revealed = session.get("revealed", {})

    return {
        "correct_diagnosis": correct_diagnosis,
        "diagnosis_correct": keyword_correct,
        "differential": case.get("differential", []),
        "reasoning_quality": 3,
        "efficiency_score": max(1, 5 - max(0, turns - 6)),
        "key_findings_identified": [],
        "missed_findings": key_findings,
        "premature_closure": not revealed.get("exam") and not revealed.get("labs"),
        "strengths": "Completed the case." if keyword_correct else "Attempted a diagnosis.",
        "improvements": "Try to elicit all key findings before committing to a diagnosis.",
        "overall_grade": "B" if keyword_correct else "D",
    }


# ── Phase D: Quiz generation ────────────────────────────────────────

QUIZ_PROMPT = """\
You are creating a medical education quiz based on this clinical case.

Case: A patient presents with: {chief_complaint}
Background: {background}
Diagnosis: {diagnosis}
Key findings: {key_findings}

Generate exactly 3 multiple-choice questions about this case.
Return ONLY a valid JSON array — no extra text:
[
  {{
    "stem": "Question text here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer_index": 0,
    "explanation": "Brief explanation of why this is correct"
  }}
]

Question types to include:
1. "What is the most likely diagnosis?" (with the correct diagnosis and 3 plausible distractors)
2. "What is the most important next step?" (diagnostic or therapeutic)
3. "Which finding is most significant?" (key differentiating feature)"""


def generate_quiz(case: dict) -> list[dict]:
    """Generate MCQs from the case for the quiz tab."""
    key_findings = case.get("key_findings", [])

    result = _llm_call(
        "You are a medical quiz generator. Return only valid JSON.",
        QUIZ_PROMPT.format(
            chief_complaint=case.get("chief_complaint", ""),
            background=case.get("background", ""),
            diagnosis=case.get("diagnosis", ""),
            key_findings=", ".join(key_findings) if key_findings else "Not specified",
        ),
        temperature=0.5,
        max_tokens=600,
    )

    if result:
        try:
            raw = result
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            questions = json.loads(raw)
            if isinstance(questions, list):
                return questions
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback quiz
    diagnosis = case.get("diagnosis", "Unknown")
    diff = case.get("differential", [diagnosis])
    options = (diff + ["None of the above"])[:4]
    while len(options) < 4:
        options.append("Other")

    return [{
        "stem": f"Based on the patient's presentation, what is the most likely diagnosis?",
        "options": options,
        "answer_index": 0,
        "explanation": f"The correct diagnosis is {diagnosis}.",
    }]


# ── Phase D: Differential checking ──────────────────────────────────

def check_differential(case: dict, hypotheses: list[str]) -> list[dict]:
    """Check the doctor's differential hypotheses against the case."""
    diagnosis = case.get("diagnosis", "").lower()
    differential = [d.lower() for d in case.get("differential", [])]
    diag_words = [w for w in diagnosis.split() if len(w) > 4]

    results = []
    for hyp in hypotheses:
        hyp_lower = hyp.lower().strip()
        if not hyp_lower:
            continue

        # Check if it matches the correct diagnosis
        if any(w in hyp_lower for w in diag_words):
            level = "correct"
        elif any(hyp_lower in d or d in hyp_lower for d in differential):
            level = "plausible"
        else:
            level = "unlikely"

        results.append({"hypothesis": hyp, "match_level": level})

    return results


# ── Public entry point ────────────────────────────────────────────────

def run_patient_sim(session: dict, doctor_message: str) -> dict:
    """Process one turn of the doctor-patient conversation."""
    case = session.get("case", {})
    messages = list(session.get("messages", []))
    revealed = dict(session.get("revealed", {"history": False, "exam": False, "labs": False}))
    turns = session.get("turns", 0) + 1
    tests_ordered = list(session.get("tests_ordered", []))

    messages.append({"role": "doctor", "content": doctor_message})

    action_type = _classify_action(doctor_message)
    evaluation = None
    session_complete = session.get("session_complete", False)

    # Track what's been revealed
    if action_type == "ask_history":
        revealed["history"] = True
    elif action_type == "order_exam":
        revealed["exam"] = True
    elif action_type == "order_labs":
        revealed["labs"] = True
        # Track specific tests mentioned
        lab_keywords = ["cbc", "cmp", "x-ray", "ct", "mri", "ecg", "ekg",
                        "ultrasound", "echo", "blood work", "urine", "culture"]
        for kw in lab_keywords:
            if kw in doctor_message.lower() and kw not in tests_ordered:
                tests_ordered.append(kw)

    if action_type == "submit_diagnosis":
        session_complete = True
        evaluation = _evaluate_diagnosis(case, doctor_message, {
            **session, "messages": messages, "turns": turns, "revealed": revealed,
        })
        if evaluation.get("diagnosis_correct"):
            response = (
                f"[Session complete] Correct! The diagnosis is {evaluation['correct_diagnosis']}."
            )
        else:
            response = (
                f"[Session complete] Not quite. The diagnosis was {evaluation['correct_diagnosis']}."
            )
    elif action_type == "request_hint":
        response = _generate_hint(case, messages[:-1], revealed)
    else:
        response = _generate_patient_response(case, messages[:-1], action_type, doctor_message, revealed)

    messages.append({"role": "patient", "content": response})

    updated_session = {
        **session,
        "messages": messages,
        "session_complete": session_complete,
        "revealed": revealed,
        "turns": turns,
        "tests_ordered": tests_ordered,
    }

    return {
        "session": updated_session,
        "response": response,
        "action_type": action_type,
        "revealed": revealed,
        "evaluation": evaluation,
    }
