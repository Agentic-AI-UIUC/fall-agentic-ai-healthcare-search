
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

from dotenv import load_dotenv
load_dotenv()  # Loads GROQ_API_KEY, SENDER_EMAIL, SENDER_PASSWORD from .env

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from pipeline.main import run_pipeline
from pipeline.email_sender import process_and_send_pre_medical
from pipeline.main import run_agent
from pipeline.agents.intake_agent import run_intake_step

# --------------------------------------------------
# Paths / config
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = BASE_DIR / "uploads"

UPLOAD_DIR.mkdir(exist_ok=True)

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