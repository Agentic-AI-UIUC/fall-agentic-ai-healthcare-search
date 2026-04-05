
"""
This file is the Flask backend that connects the frontend to the retrieval pipeline.
It serves the frontend files, exposes API routes like /api/health, /api/chat, 
and /api/upload, accepts user questions from the frontend, calls retrieve_chunks() 
from pipeline/retriever.py, formats the retrieved results into source cards, and returns 
JSON responses back to the frontend. Right now it uses retrieval-based answer construction
as a temporary stand-in for a full generator model, so it acts as the bridge between the 
UI and the backend RAG components.
 """

import os
import uuid
from datetime import datetime
from pathlib import Path

import json

from flask import Flask, jsonify, request, send_from_directory, Response
from dotenv import load_dotenv
load_dotenv()  # Loads GROQ_API_KEY, SENDER_EMAIL, SENDER_PASSWORD from .env

from werkzeug.utils import secure_filename

from pipeline.main import run_pipeline, run_agent
from pipeline.email_sender import process_and_send_pre_medical
from pipeline.agents.intake_agent import run_intake_step
from pipeline.agents.patient_sim_agent import (
    run_patient_sim, generate_case_from_chunks, new_session,
    generate_quiz, check_differential,
)

# --------------------------------------------------
# Paths / config
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = BASE_DIR / "uploads"

INTAKE_DIR = BASE_DIR / "intake_forms"

UPLOAD_DIR.mkdir(exist_ok=True)
INTAKE_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {
    "pdf", "txt", "doc", "docx", "png", "jpg", "jpeg"
}

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path=""
)

# simple in-memory stores for local dev / prototype
uploaded_docs = {}
intake_sessions = {}
doctor_sessions = {}  # session_id -> {case, messages, session_complete}


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def build_answer_from_chunks(user_message: str, chunks: list[dict]) -> str:
    """
    Temporary answer builder until generator.py / real LLM is connected.
    This makes the app usable now by turning retrieved chunks into a plain response.
    """

    if not chunks:
        return (
            "I could not find relevant medical context for that question yet. "
            "Try rewording the question or make sure the Qdrant collection is populated."
        )

    top_text = chunks[0].get("text", "").strip()
    second_text = chunks[1].get("text", "").strip() if len(chunks) > 1 else ""

    preview_1 = top_text[:700].strip()
    preview_2 = second_text[:400].strip()

    answer_parts = [
        "Here is a source-grounded explanation based on the most relevant retrieved medical text.",
        "",
        preview_1
    ]

    if preview_2:
        answer_parts.extend([
            "",
            "Additional related context:",
            preview_2
        ])

    answer_parts.extend([
        "",
        "This response is currently based on retrieved source text rather than a full LLM summary."
    ])

    return "\n".join(answer_parts)


def convert_chunks_to_sources(chunks: list[dict]) -> list[dict]:
    sources = []

    for i, chunk in enumerate(chunks, start=1):
        text = chunk.get("text", "") or ""
        score = chunk.get("score", None)
        chunk_id = chunk.get("id", None)
        chunk_source = chunk.get("source", f"Chunk {i}")

        sources.append({
            "title": f"Source: {chunk_source}" + (f" (ID {chunk_id})" if chunk_id is not None else ""),
            "snippet": text[:350].strip(),
            "score": round(float(score), 4) if score is not None else None
        })

    return sources


# --------------------------------------------------
# Frontend routes
# --------------------------------------------------

@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def serve_frontend_assets(path):
    file_path = FRONTEND_DIR / path
    if file_path.exists():
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, "index.html")


# --------------------------------------------------
# API routes
# --------------------------------------------------

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# --------------------------------------------------
# Doctor Practice Mode API
# --------------------------------------------------

@app.route("/api/doctor/session", methods=["POST"])
def doctor_new_session():
    """Start a new doctor-practice session with a freshly generated patient case."""
    try:
        data = request.get_json(silent=True) or {}
        seed_query = data.get("seed_query")  # optional speciality hint

        case = generate_case_from_chunks(seed_query)

        session_id = str(uuid.uuid4())
        doctor_sessions[session_id] = new_session(case)

        # Return public case info — diagnosis is intentionally omitted
        public_info = {
            "chief_complaint": case.get("chief_complaint", ""),
            "difficulty": case.get("difficulty", "beginner"),
        }

        return jsonify({
            "session_id": session_id,
            "case": public_info,
            "greeting": (
                "Hello, doctor. I'm glad you could see me today. "
                + case.get("chief_complaint", "I haven't been feeling well.")
            ),
        }), 200

    except Exception as e:
        return jsonify({"error": "Failed to generate case.", "details": str(e)}), 500


@app.route("/api/doctor/chat", methods=["POST"])
def doctor_chat():
    """Send a message from the doctor trainee; get a patient response."""
    try:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id")
        doctor_message = (data.get("message") or "").strip()

        if not session_id or session_id not in doctor_sessions:
            return jsonify({"error": "Invalid or expired session. Start a new case."}), 400

        if not doctor_message:
            return jsonify({"error": "Message is required."}), 400

        session = doctor_sessions[session_id]

        if session.get("session_complete"):
            return jsonify({"error": "Session is already complete. Start a new case."}), 400

        result = run_patient_sim(session, doctor_message)
        doctor_sessions[session_id] = result["session"]

        return jsonify({
            "session_id": session_id,
            "response": result["response"],
            "action_type": result["action_type"],
            "session_complete": result["session"]["session_complete"],
            "evaluation": result.get("evaluation"),
        }), 200

    except Exception as e:
        return jsonify({"error": "Doctor chat failed.", "details": str(e)}), 500


@app.route("/api/doctor/quiz", methods=["POST"])
def doctor_quiz():
    """Generate MCQs from the active case."""
    try:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id")

        if not session_id or session_id not in doctor_sessions:
            return jsonify({"error": "Invalid session."}), 400

        case = doctor_sessions[session_id]["case"]
        questions = generate_quiz(case)
        return jsonify({"questions": questions}), 200

    except Exception as e:
        return jsonify({"error": "Quiz generation failed.", "details": str(e)}), 500


@app.route("/api/doctor/differential", methods=["POST"])
def doctor_differential():
    """Check the doctor's differential hypotheses against the case."""
    try:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id")
        hypotheses = data.get("hypotheses", [])

        if not session_id or session_id not in doctor_sessions:
            return jsonify({"error": "Invalid session."}), 400

        case = doctor_sessions[session_id]["case"]
        results = check_differential(case, hypotheses)
        return jsonify({"results": results}), 200

    except Exception as e:
        return jsonify({"error": "Differential check failed.", "details": str(e)}), 500


@app.route("/api/intake", methods=["POST"])
def intake():
    try:
        data = request.get_json(silent=True) or {}

        session_id = data.get("intake_session_id")
        user_message = data.get("message")  # None on first call to start the flow

        # Load or create session
        if session_id and session_id in intake_sessions:
            session = intake_sessions[session_id]
        else:
            session_id = str(uuid.uuid4())
            session = {
                "step": "greeting",
                "form": None,
                "messages": [],
                "complete": False,
                "emergency": False,
            }

        # Strip the message if present
        if user_message is not None:
            user_message = user_message.strip()
            if not user_message:
                user_message = None

        result = run_intake_step(session, user_message)
        intake_sessions[session_id] = result

        # Save completed form to disk
        if result.get("complete") and result.get("form"):
            _save_intake_form(session_id, result["form"])

        return jsonify({
            "intake_session_id": session_id,
            "response": result.get("response", ""),
            "step": result.get("step", "greeting"),
            "step_number": result.get("step_number", 1),
            "total_steps": result.get("total_steps", 5),
            "step_label": result.get("step_label", ""),
            "intake_complete": result.get("complete", False),
            "intake_form": result.get("form") if result.get("complete") else None,
            "emergency": result.get("emergency", False),
        }), 200

    except Exception as e:
        return jsonify({
            "error": "Intake processing failed.",
            "details": str(e)
        }), 500


def _save_intake_form(session_id: str, form: dict):
    """Save the completed intake form as JSON to disk."""
    json_path = INTAKE_DIR / f"{session_id}.json"
    with open(json_path, "w") as f:
        json.dump(form, f, indent=2)


def _format_intake_text(form: dict) -> str:
    """Format intake form as a human-readable text document."""
    lines = [
        "=" * 52,
        "          PATIENT INTAKE FORM",
        "=" * 52,
        "",
        f"Date: {form.get('timestamp', 'N/A')}",
        "",
        "-" * 52,
        "CHIEF COMPLAINT",
        "-" * 52,
        form.get("chief_complaint", "Not provided"),
        "",
        "-" * 52,
        "SYMPTOM DETAILS",
        "-" * 52,
        form.get("symptoms", "Not provided"),
        "",
        "-" * 52,
        "CURRENT MEDICATIONS",
        "-" * 52,
        form.get("medications", "Not provided"),
        "",
        "-" * 52,
        "KNOWN ALLERGIES",
        "-" * 52,
        form.get("allergies", "Not provided"),
        "",
        "-" * 52,
        "PRE-EXISTING CONDITIONS / SURGERIES",
        "-" * 52,
        form.get("conditions", "Not provided"),
        "",
        "-" * 52,
        "FAMILY MEDICAL HISTORY",
        "-" * 52,
        form.get("family_history", "Not provided"),
        "",
        "-" * 52,
        "LIFESTYLE",
        "-" * 52,
        form.get("lifestyle", "Not provided"),
        "",
    ]

    if form.get("emergency_flag"):
        lines.extend([
            "!" * 52,
            "  WARNING: EMERGENCY SYMPTOMS WERE REPORTED",
            "!" * 52,
            "",
        ])

    lines.extend([
        "=" * 52,
        "Generated by MedAssist Patient Intake System",
        "This is not a medical diagnosis.",
        "=" * 52,
    ])

    return "\n".join(lines)


@app.route("/api/intake/<session_id>/download", methods=["GET"])
def download_intake(session_id):
    """Download the completed intake form as a text file."""
    # Try in-memory first, then disk
    session = intake_sessions.get(session_id)
    form = None

    if session and session.get("complete"):
        form = session.get("form")

    if not form:
        json_path = INTAKE_DIR / f"{session_id}.json"
        if json_path.exists():
            with open(json_path) as f:
                form = json.load(f)

    if not form:
        return jsonify({"error": "Intake form not found or not yet complete."}), 404

    text = _format_intake_text(form)

    return Response(
        text,
        mimetype="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=intake_form_{session_id[:8]}.txt"
        },
    )


@app.route("/api/intake/<session_id>/json", methods=["GET"])
def get_intake_json(session_id):
    """Get the completed intake form as JSON (for future agent use)."""
    session = intake_sessions.get(session_id)
    form = None

    if session and session.get("complete"):
        form = session.get("form")

    if not form:
        json_path = INTAKE_DIR / f"{session_id}.json"
        if json_path.exists():
            with open(json_path) as f:
                form = json.load(f)

    if not form:
        return jsonify({"error": "Intake form not found or not yet complete."}), 404

    return jsonify({"intake_form": form}), 200


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}

        user_message = (data.get("message") or "").strip()
        uploaded_document_id = data.get("uploaded_document_id")

        if not user_message:
            return jsonify({"error": "Message is required."}), 400

        # Augment query with document context if a file was uploaded
        if uploaded_document_id and uploaded_document_id in uploaded_docs:
            doc_meta = uploaded_docs[uploaded_document_id]
            user_message = (
                f"{user_message}\n\n"
                f"Uploaded document context: {doc_meta['original_name']}"
            )

        # Run the LangGraph agent pipeline
        result = run_agent(
            user_message=user_message,
            conversation_id=data.get("conversation_id"),
            uploaded_document_id=uploaded_document_id,
        )

        return jsonify({
            "answer": result["generated_answer"],
            "sources": result["sources"],
            "emergency": result.get("emergency_flag", False),
        }), 200

    except Exception as e:
        return jsonify({
            "error": "Failed to process chat request.",
            "details": str(e)
        }), 500


@app.route("/api/upload", methods=["POST"])
def upload():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part in request."}), 400

        file = request.files["file"]

        if file.filename == "":
            return jsonify({"error": "No file selected."}), 400

        if not allowed_file(file.filename):
            return jsonify({
                "error": "Unsupported file type."
            }), 400

        original_name = file.filename
        safe_name = secure_filename(original_name)

        doc_id = str(uuid.uuid4())
        ext = safe_name.rsplit(".", 1)[1].lower()
        stored_name = f"{doc_id}.{ext}"
        save_path = UPLOAD_DIR / stored_name

        file.save(save_path)

        uploaded_docs[doc_id] = {
            "document_id": doc_id,
            "original_name": original_name,
            "stored_name": stored_name,
            "path": str(save_path),
            "uploaded_at": datetime.utcnow().isoformat() + "Z"
        }

        return jsonify({
            "document_id": doc_id,
            "summary": f"{original_name} uploaded successfully."
        }), 200

    except Exception as e:
        return jsonify({
            "error": "Upload failed.",
            "details": str(e)
        }), 500

@app.route("/api/pre_medical", methods=["POST"])
def pre_medical():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON payload provided."}), 400
        
        result = process_and_send_pre_medical(data)
        
        if result.get("status") == "error":
            return jsonify({"error": result.get("message")}), 500
            
        return jsonify({"summary": result.get("message")}), 200

    except Exception as e:
        return jsonify({
            "error": "Pre-medical form processing failed.",
            "details": str(e)
        }), 500


# --------------------------------------------------
# Run app
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)