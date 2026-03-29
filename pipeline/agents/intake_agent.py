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

STEPS = ["greeting", "symptoms", "history", "lifestyle", "summary"]

STEP_LABELS = {
    "greeting": "Chief Complaint",
    "symptoms": "Symptom Details",
    "history": "Medical History",
    "lifestyle": "Lifestyle",
    "summary": "Review & Confirm",
}

SCRIPTED_QUESTIONS = {
    "greeting": (
        "Hi! I'll help you create your intake form. "
        "Let's start — what's the main reason for your visit today?"
    ),
    "symptoms": (
        "Thanks for sharing that. Let me get a few more details:\n\n"
        "- When did this start?\n"
        "- On a scale of 1-10, how severe is it?\n"
        "- Is it constant or does it come and go?\n"
        "- What makes it better or worse?"
    ),
    "history": (
        "That's helpful. Now a few questions about your medical background:\n\n"
        "- Are you currently taking any medications?\n"
        "- Do you have any known allergies?\n"
        "- Any pre-existing conditions or past surgeries?\n"
        "- Any relevant family medical history?"
    ),
    "lifestyle": (
        "Almost done! A couple of lifestyle questions:\n\n"
        "- Do you smoke or drink alcohol?\n"
        "- How often do you exercise?\n"
        "- Any recent travel?"
    ),
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
        "symptoms": "",
        "medications": "",
        "allergies": "",
        "conditions": "",
        "family_history": "",
        "lifestyle": "",
        "emergency_flag": False,
        "timestamp": "",
    }


def build_summary(form: dict) -> str:
    """Build a readable summary of the intake form."""
    lines = [
        "Here's a summary of your intake form:\n",
        f"**Chief complaint:** {form.get('chief_complaint', 'Not provided')}",
        f"**Symptom details:** {form.get('symptoms', 'Not provided')}",
        f"**Medications:** {form.get('medications', 'Not provided')}",
        f"**Allergies:** {form.get('allergies', 'Not provided')}",
        f"**Conditions/surgeries:** {form.get('conditions', 'Not provided')}",
        f"**Family history:** {form.get('family_history', 'Not provided')}",
        f"**Lifestyle:** {form.get('lifestyle', 'Not provided')}",
        "\nDoes everything look correct? Type **yes** to finalize, "
        "or tell me what you'd like to change.",
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
        greeting = SCRIPTED_QUESTIONS["greeting"]
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
    if step == "greeting":
        form["chief_complaint"] = user_message
        # Try LLM extraction for richer data
        llm_updates = _extract_with_llm("greeting", user_message, form)
        form.update(llm_updates)

    elif step == "symptoms":
        form["symptoms"] = user_message
        llm_updates = _extract_with_llm("symptoms", user_message, form)
        form.update(llm_updates)

    elif step == "history":
        # Parse the multi-part response
        form["medications"] = user_message
        form["conditions"] = user_message
        llm_updates = _extract_with_llm("history", user_message, form)
        if llm_updates:
            form.update(llm_updates)

    elif step == "lifestyle":
        form["lifestyle"] = user_message
        llm_updates = _extract_with_llm("lifestyle", user_message, form)
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
            }
        else:
            # User wants to change something — stay on summary
            change_msg = (
                "No problem! Please tell me what you'd like to update, "
                "and I'll adjust the form."
            )
            # Try LLM to handle the correction
            llm_updates = _extract_with_llm("correction", user_message, form)
            if llm_updates:
                form.update(llm_updates)
                summary = build_summary(form)
                change_msg = f"I've updated the form. {summary}"

            messages.append({"role": "assistant", "text": change_msg})
            return {
                **session,
                "step": "summary",
                "form": form,
                "messages": messages,
                "complete": False,
                "emergency": form.get("emergency_flag", False),
                "step_number": get_step_number("summary"),
                "total_steps": len(STEPS),
                "step_label": STEP_LABELS["summary"],
                "response": change_msg,
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
    else:
        # Try LLM-generated follow-up first, fall back to scripted
        response = _generate_followup_with_llm(next_step, user_message, form)
        if not response:
            response = SCRIPTED_QUESTIONS.get(next_step, "Please continue.")

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
    }
