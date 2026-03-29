
/* 
This file handles all frontend interaction and state management. 
It manages sending chat messages, rendering assistant responses, 
showing retrieved sources, storing conversation history in localStorage,
switching between saved chats, handling document upload UI, checking
backend health, and making real fetch requests to the Flask API 
endpoints. In other words, this is the file that makes the static HTML
interface behave like a real application.
*/
const STORAGE_KEY = "healthcare_frontend_live_v1";

const API = {
  health: "/api/health",
  chat: "/api/chat",
  upload: "/api/upload",
  preMedical: "/api/pre_medical",
};

const elements = {
  conversationList: document.getElementById("conversationList"),
  chatMessages: document.getElementById("chatMessages"),
  chatTitle: document.getElementById("chatTitle"),
  backendStatusText: document.getElementById("backendStatusText"),
  composerStatus: document.getElementById("composerStatus"),
  messageInput: document.getElementById("messageInput"),
  sendBtn: document.getElementById("sendBtn"),
  newChatBtn: document.getElementById("newChatBtn"),
  clearMessagesBtn: document.getElementById("clearMessagesBtn"),
  mentionUploadBtn: document.getElementById("mentionUploadBtn"),
  toggleReviewBtn: document.getElementById("toggleReviewBtn"),
  scrollBottomBtn: document.getElementById("scrollBottomBtn"),
  fileInput: document.getElementById("fileInput"),
  fileCard: document.getElementById("fileCard"),
  suggestions: document.getElementById("suggestions"),
  reviewPanel: document.getElementById("reviewPanel"),
  
  // Pre-Medical Modal
  preMedicalBtn: document.getElementById("preMedicalBtn"),
  preMedicalModal: document.getElementById("preMedicalModal"),
  closeModalBtn: document.getElementById("closeModalBtn"),
  preMedicalForm: document.getElementById("preMedicalForm"),
  submitFormBtn: document.getElementById("submitFormBtn"),
  formStatus: document.getElementById("formStatus"),
};

let state = loadState();
let backendOnline = false;
let requestInFlight = false;

init();

async function init() {
  bindEvents();
  ensureConversationExists();
  renderAll();
  autoResizeTextarea();
  await checkBackendHealth();
}

function bindEvents() {
  elements.sendBtn.addEventListener("click", handleSend);
  elements.newChatBtn.addEventListener("click", createNewConversation);
  elements.clearMessagesBtn.addEventListener("click", clearCurrentConversation);
  elements.mentionUploadBtn.addEventListener("click", insertUploadPrompt);
  elements.toggleReviewBtn.addEventListener("click", toggleReviewPanel);
  elements.scrollBottomBtn.addEventListener("click", scrollMessagesToBottom);

  elements.preMedicalBtn.addEventListener("click", () => {
    elements.preMedicalModal.classList.remove("hidden");
  });
  
  elements.closeModalBtn.addEventListener("click", () => {
    elements.preMedicalModal.classList.add("hidden");
  });

  elements.submitFormBtn.addEventListener("click", handlePreMedicalSubmit);

  elements.messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  });

  elements.messageInput.addEventListener("input", autoResizeTextarea);

  elements.fileInput.addEventListener("change", handleFileUpload);

  elements.suggestions.addEventListener("click", (event) => {
    const button = event.target.closest(".suggestion-chip");
    if (!button) return;
    elements.messageInput.value = button.textContent.trim();
    autoResizeTextarea();
    elements.messageInput.focus();
  });

  document.querySelectorAll(".breakdown-card").forEach((button) => {
    button.addEventListener("click", () => {
      elements.messageInput.value = button.dataset.prompt || "";
      autoResizeTextarea();
      elements.messageInput.focus();
    });
  });
}

function loadState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return {
      conversations: [],
      currentConversationId: null,
      uploadedFile: null,
    };
  }

  try {
    return JSON.parse(raw);
  } catch {
    return {
      conversations: [],
      currentConversationId: null,
      uploadedFile: null,
    };
  }
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function ensureConversationExists() {
  if (!state.conversations.length) {
    const convo = makeConversation("New conversation");
    state.conversations.unshift(convo);
    state.currentConversationId = convo.id;
    saveState();
  }

  if (!getCurrentConversation()) {
    state.currentConversationId = state.conversations[0].id;
    saveState();
  }
}

function makeConversation(title = "New conversation") {
  return {
    id: crypto.randomUUID(),
    title,
    createdAt: new Date().toISOString(),
    messages: [],
  };
}

function getCurrentConversation() {
  return state.conversations.find((c) => c.id === state.currentConversationId) || null;
}

function createNewConversation() {
  const convo = makeConversation("New conversation");
  state.conversations.unshift(convo);
  state.currentConversationId = convo.id;
  saveState();
  renderAll();
  elements.messageInput.focus();
}

function switchConversation(id) {
  state.currentConversationId = id;
  saveState();
  renderAll();
}

function clearCurrentConversation() {
  const convo = getCurrentConversation();
  if (!convo) return;
  convo.messages = [];
  convo.title = "New conversation";
  saveState();
  renderAll();
}

function insertUploadPrompt() {
  const fileName = state.uploadedFile?.name || "my uploaded medical document";
  elements.messageInput.value = `Please explain the important parts of ${fileName} in simple language.`;
  autoResizeTextarea();
  elements.messageInput.focus();
}

function toggleReviewPanel() {
  elements.reviewPanel.classList.toggle("force-open");
}

function scrollMessagesToBottom() {
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

async function checkBackendHealth() {
  try {
    const response = await fetch(API.health, { method: "GET" });
    backendOnline = response.ok;
  } catch {
    backendOnline = false;
  }

  elements.backendStatusText.textContent = backendOnline
    ? "Backend connected"
    : "Backend offline — frontend is loaded, but Flask endpoints are not responding";

  elements.composerStatus.textContent = backendOnline ? "Ready" : "Waiting for backend";
}

async function handleFileUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  state.uploadedFile = {
    name: file.name,
    size: formatFileSize(file.size),
    type: file.type || "Unknown file type",
    uploadedAt: new Date().toISOString(),
  };

  renderFileCard();
  saveState();

  if (!backendOnline) return;

  const formData = new FormData();
  formData.append("file", file);

  try {
    elements.composerStatus.textContent = "Uploading document...";
    const response = await fetch(API.upload, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error("Upload failed");
    }

    const data = await response.json();

    state.uploadedFile = {
      ...state.uploadedFile,
      serverId: data.document_id || null,
      summary: data.summary || null,
    };

    saveState();
    renderFileCard();
    elements.composerStatus.textContent = "Document uploaded";
  } catch {
    elements.composerStatus.textContent = "Upload failed";
  }
}

async function handleSend() {
  const text = elements.messageInput.value.trim();
  if (!text || requestInFlight) return;

  const convo = getCurrentConversation();
  if (!convo) return;

  convo.messages.push({
    id: crypto.randomUUID(),
    role: "user",
    text,
    timestamp: new Date().toISOString(),
  });

  if (convo.title === "New conversation") {
    convo.title = makeTitleFromMessage(text);
  }

  elements.messageInput.value = "";
  autoResizeTextarea();
  renderAll();

  const typingId = crypto.randomUUID();
  convo.messages.push({
    id: typingId,
    role: "typing",
    timestamp: new Date().toISOString(),
  });

  requestInFlight = true;
  saveState();
  renderMessages();
  scrollMessagesToBottom();

  try {
    if (!backendOnline) {
      await checkBackendHealth();
    }

    if (!backendOnline) {
      throw new Error("Backend is not available. Start your Flask app and API routes.");
    }

    elements.composerStatus.textContent = "Fetching answer...";

    const response = await fetch(API.chat, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: text,
        conversation_id: convo.id,
        uploaded_document_id: state.uploadedFile?.serverId || null,
      }),
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();

    convo.messages = convo.messages.filter((m) => m.id !== typingId);
    convo.messages.push({
      id: crypto.randomUUID(),
      role: "assistant",
      text: data.answer || "No answer returned.",
      sources: normalizeSources(data.sources),
      timestamp: new Date().toISOString(),
    });

    elements.composerStatus.textContent = "Ready";
  } catch (error) {
    convo.messages = convo.messages.filter((m) => m.id !== typingId);
    convo.messages.push({
      id: crypto.randomUUID(),
      role: "error",
      text: error.message || "Something went wrong while fetching the answer.",
      timestamp: new Date().toISOString(),
    });

    elements.composerStatus.textContent = "Request failed";
  } finally {
    requestInFlight = false;
    saveState();
    renderAll();
    scrollMessagesToBottom();
  }
}

function normalizeSources(sources) {
  if (!Array.isArray(sources)) return [];

  return sources.map((source, index) => ({
    title: source.title || source.name || `Source ${index + 1}`,
    snippet: source.snippet || source.text || source.preview || "",
    score: source.score != null ? String(source.score) : "N/A",
  }));
}

function renderAll() {
  renderConversationList();
  renderMessages();
  renderFileCard();
}

function renderConversationList() {
  elements.conversationList.innerHTML = "";

  state.conversations.forEach((conversation) => {
    const button = document.createElement("button");
    button.className = `conversation-item ${conversation.id === state.currentConversationId ? "active" : ""}`;
    button.type = "button";

    const lastMessageCount = conversation.messages.filter((m) => m.role !== "typing").length;
    const dateLabel = formatRelativeDate(conversation.createdAt);

    button.innerHTML = `
      <div class="conversation-title">${escapeHtml(conversation.title)}</div>
      <div class="conversation-meta">
        <span>${dateLabel}</span>
        <span>${lastMessageCount} messages</span>
      </div>
    `;

    button.addEventListener("click", () => switchConversation(conversation.id));
    elements.conversationList.appendChild(button);
  });
}

function renderMessages() {
  const convo = getCurrentConversation();
  elements.chatMessages.innerHTML = "";

  const datePill = document.createElement("div");
  datePill.className = "date-pill";
  datePill.textContent = "Today";
  elements.chatMessages.appendChild(datePill);

  elements.chatTitle.textContent = convo?.title || "New conversation";

  if (!convo || !convo.messages.length) {
    const intro = document.createElement("div");
    intro.className = "intro-card";
    intro.innerHTML = `
      <div class="mini-label">Start here</div>
      <p>
        Ask a medical question or upload a document for explanation.
        Assistant answers are expected to include source cards returned by your backend.
      </p>
    `;
    elements.chatMessages.appendChild(intro);
    return;
  }

  convo.messages.forEach((message) => {
    if (message.role === "typing") {
      elements.chatMessages.appendChild(renderTypingMessage(message));
    } else if (message.role === "error") {
      elements.chatMessages.appendChild(renderErrorMessage(message));
    } else {
      elements.chatMessages.appendChild(renderMessage(message));
    }
  });
}

function renderMessage(message) {
  const row = document.createElement("div");
  row.className = `message-row ${message.role === "user" ? "user" : "assistant"}`;

  const avatarLabel = message.role === "user" ? "N" : "AI";
  const authorLabel = message.role === "user" ? "You" : "Healthcare Assistant";

  row.innerHTML = `
    <div class="message-avatar">${avatarLabel}</div>
    <div class="message-body">
      <div class="message-meta">
        <span>${authorLabel}</span>
        <span>${formatTime(message.timestamp)}</span>
      </div>
      <div class="bubble">
        ${renderParagraphs(message.text)}
        ${message.role === "assistant" ? renderSources(message.sources || []) : ""}
      </div>
    </div>
  `;

  return row;
}

function renderTypingMessage(message) {
  const row = document.createElement("div");
  row.className = "message-row assistant";

  row.innerHTML = `
    <div class="message-avatar">AI</div>
    <div class="message-body">
      <div class="message-meta">
        <span>Healthcare Assistant</span>
        <span>${formatTime(message.timestamp)}</span>
      </div>
      <div class="bubble typing-bubble">
        <span>Drafting answer</span>
        <span class="typing-dots"><span></span><span></span><span></span></span>
      </div>
    </div>
  `;

  return row;
}

function renderErrorMessage(message) {
  const wrap = document.createElement("div");
  wrap.className = "error-card";
  wrap.innerHTML = `
    <div class="mini-label">Error</div>
    <p>${escapeHtml(message.text)}</p>
  `;
  return wrap;
}

function renderSources(sources) {
  if (!sources.length) return "";

  const cards = sources
    .map(
      (source) => `
        <div class="source-card">
          <div class="mini-label">Source</div>
          <div class="source-card-title">${escapeHtml(source.title)}</div>
          <div class="source-snippet">${escapeHtml(source.snippet)}</div>
          <div class="source-score">Relevance score: ${escapeHtml(source.score)}</div>
        </div>
      `
    )
    .join("");

  return `<div class="sources-wrap">${cards}</div>`;
}

function renderFileCard() {
  if (!state.uploadedFile) {
    elements.fileCard.className = "file-card empty";
    elements.fileCard.innerHTML = `
      <div class="file-name">No file uploaded yet</div>
      <p class="file-meta">Upload a file to begin document review.</p>
    `;
    return;
  }

  elements.fileCard.className = "file-card";
  elements.fileCard.innerHTML = `
    <div class="file-name">${escapeHtml(state.uploadedFile.name)}</div>
    <p class="file-meta">${escapeHtml(state.uploadedFile.type)} · ${state.uploadedFile.size}</p>
    <p class="file-meta">Uploaded ${formatRelativeDate(state.uploadedFile.uploadedAt)}</p>
    ${state.uploadedFile.summary ? `<p class="file-meta">${escapeHtml(state.uploadedFile.summary)}</p>` : ""}
  `;
}

function autoResizeTextarea() {
  const textarea = elements.messageInput;
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
}

function renderParagraphs(text) {
  return text
    .split("\n")
    .filter(Boolean)
    .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
    .join("");
}

function makeTitleFromMessage(text) {
  return text.length > 36 ? `${text.slice(0, 36)}...` : text;
}

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatRelativeDate(iso) {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now - date;
  const dayMs = 24 * 60 * 60 * 1000;

  if (diffMs < dayMs) return "Today";
  if (diffMs < dayMs * 2) return "Yesterday";

  return date.toLocaleDateString([], {
    month: "short",
    day: "numeric",
  });
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function handlePreMedicalSubmit() {
  const formStatus = elements.formStatus;
  
  if (!elements.preMedicalForm.checkValidity()) {
    elements.preMedicalForm.reportValidity();
    return;
  }

  const payload = {
    doctorEmail: document.getElementById("doctorEmail").value,
    
    // 1. Basic Demographics
    patientName: document.getElementById("patientName").value,
    patientDob: document.getElementById("patientDob").value,
    patientGender: document.getElementById("patientGender").value,
    patientContact: document.getElementById("patientContact").value,
    emergencyContact: document.getElementById("emergencyContact").value,
    
    // 2. Insurance & Administrative
    insuranceInfo: document.getElementById("insuranceInfo").value,
    referringPhysician: document.getElementById("referringPhysician").value,
    
    // 3. Medical History
    pastIllnesses: document.getElementById("pastIllnesses").value,
    surgeries: document.getElementById("surgeries").value,
    immunizations: document.getElementById("immunizations").value,
    
    // 4. Medications & Allergies
    currentMeds: document.getElementById("currentMeds").value,
    allergies: document.getElementById("allergies").value,
    
    // 5. Family History
    familyHistory: document.getElementById("familyHistory").value,
    
    // 6. Social & Lifestyle
    lifestyleInfo: document.getElementById("lifestyleInfo").value,
    occupation: document.getElementById("occupation").value,
    livingSituation: document.getElementById("livingSituation").value,
    
    // 7. Mental Health
    mentalHealth: document.getElementById("mentalHealth").value,
    
    // 8. Current Symptoms
    reason: document.getElementById("visitReason").value,
    symptoms: document.getElementById("symptomDetails").value,
    
    // 9. Review of Systems
    reviewOfSystems: document.getElementById("reviewOfSystems").value,
    
    // 10. Specialty-Specific
    specialtyQuestions: document.getElementById("specialtyQuestions").value,
  };

  formStatus.textContent = "Sending...";
  formStatus.className = "form-status";
  elements.submitFormBtn.disabled = true;

  try {
    const response = await fetch(API.preMedical, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Failed to process form");
    }

    formStatus.textContent = "Sent successfully!";
    formStatus.className = "form-status success";
    elements.preMedicalForm.reset();
    
    setTimeout(() => {
      elements.preMedicalModal.classList.add("hidden");
      formStatus.textContent = "";
    }, 2000);

  } catch (error) {
    formStatus.textContent = error.message;
    formStatus.className = "form-status error";
  } finally {
    elements.submitFormBtn.disabled = false;
  }
}