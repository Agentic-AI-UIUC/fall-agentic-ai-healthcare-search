import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename

from pipeline.main import run_agent
from pipeline.agents.intake_agent import run_intake_step

# --------------------------------------------------
# Config
# --------------------------------------------------

UPLOAD_DIR = Path(PROJECT_ROOT) / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "txt", "doc", "docx", "png", "jpg", "jpeg"}

app = Flask(__name__)
CORS(app)

# In-memory stores (local dev / prototype)
uploaded_docs = {}
intake_sessions = {}


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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
        user_message = data.get("message")

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
            return jsonify({"error": "Unsupported file type."}), 400

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
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

        return jsonify({
            "document_id": doc_id,
            "summary": f"{original_name} uploaded successfully.",
        }), 200

    except Exception as e:
        return jsonify({
            "error": "Upload failed.",
            "details": str(e)
        }), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
