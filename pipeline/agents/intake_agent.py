"""
Patient intake agent — a multi-turn conversational flow that collects
symptoms, medical history, and lifestyle info, then produces a structured
intake form. Works in fallback mode (scripted questions) when no LLM is available.
"""

from datetime import datetime, timezone

from pipeline.generator import get_llm
from pipeline.prompts import INTAKE_STEP_PROMPT, INTAKE_EXTRACT_PROMPT

EMERGENCY_KEYWORDS = [
    "chest pain", "can't breathe", "cannot breathe", "difficulty breathing",
    "stroke", "seizure", "unconscious", "suicidal", "suicide",
    "overdose", "severe bleeding", "coughing blood", "facial drooping",
]

STEPS = [
    "greeting", "demographics", "emergency_contact", "history", "family_history", 
    "lifestyle", "activity", "medications", "objectives", "summary"
]

STEP_LABELS = {
    "greeting": "Chief Complaint",
    "demographics": "Demographics & Info",
    "emergency_contact": "Emergency & Physician",
    "history": "Medical History",
    "family_history": "Family History",
    "lifestyle": "Lifestyle & Habits",
    "activity": "Activity & Physical",
    "medications": "Medications",
    "objectives": "Objectives",
    "summary": "Review & Confirm",
}

SCRIPTED_QUESTIONS = {
    "greeting": {
        "text": "Hi! I'll help you create your intake form. Let's start — what's the main reason for your visit today?",
        "options": ["General Checkup", "Pain/Discomfort", "Follow-up", "Medication Refill", "Other (Please type)"]
    },
    "demographics": {
        "text": "Hi! Let's get your medical file started. Could you provide your full name, date of birth, and any insurance provider details?",
        "options": []
    },
    "emergency_contact": {
        "text": "Thanks. Who should we contact in case of an emergency (name/phone), and who is your primary care physician?",
        "options": []
    },
    "history": {
        "text": "Do you have any past or present medical conditions? Please select from the common ones below, or type any others.",
        "options": ["None", "High blood pressure", "Heart problems", "Diabetes / High cholesterol", "Lung issues / Asthma", "Recent operations", "Other (Please type)"]
    },
    "family_history": {
        "text": "Do any of your first-degree relatives (parents, siblings, children) have a history of major conditions?",
        "options": ["None", "Heart disease / attack", "High blood pressure", "Diabetes", "Other (Please type)"]
    },
    "lifestyle": {
        "text": "Do you currently smoke or use tobacco? How would you describe your nutritional habits and weight trends over the past year?",
        "options": ["Don't smoke, healthy diet", "Don't smoke, average diet", "Smoke, healthy diet", "Smoke, average/poor diet", "Other"]
    },
    "activity": {
        "text": "Do you exercise regularly? Can you walk 4 miles briskly without fatigue, and are there any bone/muscle injuries that interfere?",
        "options": ["Yes, exercise regularly", "No regular exercise", "Have physical injuries/limitations", "Other"]
    },
    "medications": {
        "text": "Are you currently taking any prescription medications or over-the-counter supplements?",
        "options": ["None", "Vitamins / Supplements only", "Yes (Please list)"]
    },
    "objectives": {
        "text": "Finally, what are your primary personal health and fitness objectives for this program?",
        "options": ["Improve general fitness", "Lose weight", "Manage medical condition", "Recover from injury", "Other"]
    },
    "summary": {
        "text": "Thank you. Please review your summary. Does everything look correct?",
        "options": ["Looks good", "I need to change something"]
    }
}


def check_emergency(text: str) -> bool:
    """Check if user text contains emergency keywords."""
    lower = text.lower()
    return any(kw in lower for kw in EMERGENCY_KEYWORDS)


def get_step_index(step: str) -> int:
    try:
        return STEPS.index(step)
    except ValueError:
        return 0


def get_step_number(step: str) -> int:
    """1-based step number for display."""
    return get_step_index(step) + 1


def make_empty_form() -> dict:
    return {
        "chief_complaint": "",
        "demographics": "",
        "emergency_contact": "",
        "history": "",
        "family_history": "",
        "lifestyle": "",
        "activity": "",
        "medications": "",
        "objectives": "",
        "emergency_flag": False,
        "timestamp": "",
    }


def build_summary(form: dict) -> str:
    """Build a readable summary of the intake form."""
    lines = [
        "Here's a summary of your intake form:\n",
        f"**Reason for Visit:** {form.get('chief_complaint', 'Not provided')}",
        f"**Demographics:** {form.get('demographics', 'Not provided')}",
        f"**Emergency / Physician:** {form.get('emergency_contact', 'Not provided')}",
        f"**Past Medical History:** {form.get('history', 'Not provided')}",
        f"**Family History:** {form.get('family_history', 'Not provided')}",
        f"**Lifestyle:** {form.get('lifestyle', 'Not provided')}",
        f"**Activity / Physical:** {form.get('activity', 'Not provided')}",
        f"**Medications:** {form.get('medications', 'Not provided')}",
        f"**Objectives:** {form.get('objectives', 'Not provided')}",
        "\nDoes everything look correct? Click \"Looks good\" to finalize, "
        "or click \"I need to change something\".",
    ]
    return "\n".join(lines)


def _extract_with_llm(step: str, user_message: str, form: dict) -> dict:
    """Use the LLM to extract structured info from the user's response."""
    try:
        client = get_llm()
        prompt = INTAKE_EXTRACT_PROMPT.format(
            step=step,
            user_message=user_message,
            current_form=str(form),
        )
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=256,
        )
        raw = (response.choices[0].message.content or "").strip()
        # The LLM should return key: value lines. Parse them.
        updates = {}
        for line in raw.split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()
                if key in form and value:
                    updates[key] = value
        return updates
    except (ValueError, Exception):
        return {}


def _generate_followup_with_llm(step: str, user_message: str, form: dict) -> str | None:
    """Use LLM to generate a context-aware follow-up question."""
    try:
        client = get_llm()
        prompt = INTAKE_STEP_PROMPT.format(
            step=step,
            step_description=STEP_LABELS.get(step, step),
            user_message=user_message,
            current_form=str(form),
        )
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=256,
        )
        return (response.choices[0].message.content or "").strip()
    except (ValueError, Exception):
        return None


def run_intake_step(
    session: dict,
    user_message: str | None = None,
) -> dict:
    """
    Process one turn of the intake conversation.

    Args:
        session: The current intake session state dict.
                 Keys: step, form, messages, complete, emergency
        user_message: The user's latest message (None for the opening turn).

    Returns:
        Updated session dict with the assistant's response appended.
    """
    step = session.get("step", "greeting")
    form = session.get("form") or make_empty_form()
    messages = session.get("messages", [])

    # ── Opening turn (no user message yet) ──
    if user_message is None:
        greeting_data = SCRIPTED_QUESTIONS["greeting"]
        greeting = greeting_data["text"]
        options = greeting_data.get("options", [])
        messages.append({"role": "assistant", "text": greeting})
        return {
            **session,
            "step": "greeting",
            "form": form,
            "messages": messages,
            "complete": False,
            "emergency": False,
            "step_number": 1,
            "total_steps": len(STEPS),
            "step_label": STEP_LABELS["greeting"],
            "response": greeting,
            "options": options,
        }

    # ── Record user message ──
    messages.append({"role": "user", "text": user_message})

    # ── Emergency check ──
    if check_emergency(user_message):
        form["emergency_flag"] = True
        emergency_msg = (
            "**URGENT: Based on what you've described, please call 911 or go to your "
            "nearest emergency room immediately.** Your safety is the top priority.\n\n"
            "If you'd still like to complete the intake form after addressing the emergency, "
            "you can continue below."
        )
        messages.append({"role": "assistant", "text": emergency_msg})
        return {
            **session,
            "step": step,
            "form": form,
            "messages": messages,
            "complete": False,
            "emergency": True,
            "step_number": get_step_number(step),
            "total_steps": len(STEPS),
            "step_label": STEP_LABELS.get(step, step),
            "response": emergency_msg,
        }

    # ── Extract data from user response based on current step ──
    if step in ["greeting", "demographics", "emergency_contact", "history", "family_history", "lifestyle", "activity", "medications", "objectives"]:
        key = "chief_complaint" if step == "greeting" else step
        form[key] = user_message
        llm_updates = _extract_with_llm(step, user_message, form)
        if llm_updates:
            form.update(llm_updates)

    elif step == "summary":
        # User is confirming or requesting changes
        lower = user_message.lower().strip()
        if lower in ("yes", "y", "looks good", "correct", "confirm", "done"):
            form["timestamp"] = datetime.now(timezone.utc).isoformat()
            done_msg = (
                "Your intake form has been saved. "
                "You can now continue to the assistant where your intake "
                "information will be used as context for your questions."
            )
            messages.append({"role": "assistant", "text": done_msg})
            return {
                **session,
                "step": "complete",
                "form": form,
                "messages": messages,
                "complete": True,
                "emergency": form.get("emergency_flag", False),
                "step_number": len(STEPS),
                "total_steps": len(STEPS),
                "step_label": "Complete",
                "response": done_msg,
                "offer_scheduling": True,
            }
        else:
            # User wants to change something — start over
            change_msg = (
                "No problem! Let's start over so you can provide the correct details. "
                + SCRIPTED_QUESTIONS["greeting"]["text"]
            )
            form = make_empty_form()
            messages.append({"role": "assistant", "text": change_msg})
            return {
                **session,
                "step": "greeting",
                "form": form,
                "messages": messages,
                "complete": False,
                "emergency": False,
                "step_number": get_step_number("greeting"),
                "total_steps": len(STEPS),
                "step_label": STEP_LABELS["greeting"],
                "response": change_msg,
                "options": SCRIPTED_QUESTIONS["greeting"]["options"],
            }

    # ── Advance to next step ──
    step_idx = get_step_index(step)
    next_idx = step_idx + 1

    if next_idx >= len(STEPS):
        # We've reached summary
        next_step = "summary"
    else:
        next_step = STEPS[next_idx]

    # ── Generate the next question ──
    if next_step == "summary":
        response = build_summary(form)
        options = SCRIPTED_QUESTIONS["summary"]["options"]
    else:
        q_data = SCRIPTED_QUESTIONS.get(next_step, {})
        response = q_data.get("text", "Please continue.")
        options = q_data.get("options", [])

    messages.append({"role": "assistant", "text": response})

    return {
        **session,
        "step": next_step,
        "form": form,
        "messages": messages,
        "complete": False,
        "emergency": form.get("emergency_flag", False),
        "step_number": get_step_number(next_step),
        "total_steps": len(STEPS),
        "step_label": STEP_LABELS.get(next_step, next_step),
        "response": response,
        "options": options,
    }
