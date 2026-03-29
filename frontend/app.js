const STORAGE_KEY = "healthcare_frontend_live_v3";

const API = {
  health: "/api/health",
  chat: "/api/chat",
  upload: "/api/upload",
  intake: "/api/intake",
};

let elements = {};
let state = loadState();
let backendOnline = false;
let requestInFlight = false;
let intakeInFlight = false;

document.addEventListener("DOMContentLoaded", () => {
  elements = {
    // Landing / intake
    landingPage: document.getElementById("landingPage"),
    landingHero: document.getElementById("landingHero"),
    landingFooter: document.getElementById("landingFooter"),
    beginIntakeBtn: document.getElementById("beginIntakeBtn"),
    skipIntakeBtn: document.getElementById("skipIntakeBtn"),
    skipIntakeBtn2: document.getElementById("skipIntakeBtn2"),
    intakeChat: document.getElementById("intakeChat"),
    intakeMessages: document.getElementById("intakeMessages"),
    intakeInput: document.getElementById("intakeInput"),
    intakeSendBtn: document.getElementById("intakeSendBtn"),
    intakeStepLabel: document.getElementById("intakeStepLabel"),
    intakeProgressFill: document.getElementById("intakeProgressFill"),
    intakeStatus: document.getElementById("intakeStatus"),
    skipIntakeFromChat: document.getElementById("skipIntakeFromChat"),
    // Main app
    mainApp: document.getElementById("mainApp"),
    conversationList: document.getElementById("conversationList"),
    chatMessages: document.getElementById("chatMessages"),
    chatTitle: document.getElementById("chatTitle"),
    backendStatusText: document.getElementById("backendStatusText"),
    composerStatus: document.getElementById("composerStatus"),
    messageInput: document.getElementById("messageInput"),
    sendBtn: document.getElementById("sendBtn"),
    newChatBtn: document.getElementById("newChatBtn"),
    backToLandingBtn: document.getElementById("backToLandingBtn"),
    toggleReviewBtn: document.getElementById("toggleReviewBtn"),
    scrollBottomBtn: document.getElementById("scrollBottomBtn"),
    fileInput: document.getElementById("fileInput"),
    fileCard: document.getElementById("fileCard"),
    suggestions: document.getElementById("suggestions"),
    reviewPanel: document.getElementById("reviewPanel"),
    uploadZone: document.getElementById("uploadZone"),
  };

  init();
});

async function init() {
  bindEvents();

  if (state.hasEnteredApp) {
    showMainApp();
  } else {
    showLanding();
  }

  await checkBackendHealth();
}

function bindEvents() {
  // Landing
  elements.beginIntakeBtn.addEventListener("click", startIntake);
  elements.skipIntakeBtn.addEventListener("click", skipToApp);
  elements.skipIntakeBtn2.addEventListener("click", skipToApp);
  elements.skipIntakeFromChat.addEventListener("click", skipToApp);

  // Intake chat
  elements.intakeSendBtn.addEventListener("click", handleIntakeSend);
  elements.intakeInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleIntakeSend();
    }
  });
  elements.intakeInput.addEventListener("input", () => {
    const ta = elements.intakeInput;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`;
  });

  // Sidebar
  elements.newChatBtn.addEventListener("click", createNewConversation);
  elements.backToLandingBtn.addEventListener("click", goBackToLanding);

  // Chat
  elements.sendBtn.addEventListener("click", handleSend);
  elements.toggleReviewBtn.addEventListener("click", toggleReviewPanel);
  elements.scrollBottomBtn.addEventListener("click", scrollMessagesToBottom);

  elements.messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  });

  elements.messageInput.addEventListener("input", autoResizeTextarea);

  // File upload
  elements.fileInput.addEventListener("change", handleFileUpload);

  // Drag and drop on upload zone
  const zone = elements.uploadZone;
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("drag-over");
  });
  zone.addEventListener("dragleave", () => {
    zone.classList.remove("drag-over");
  });
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("drag-over");
    if (e.dataTransfer.files.length) {
      elements.fileInput.files = e.dataTransfer.files;
      handleFileUpload({ target: { files: e.dataTransfer.files } });
    }
  });

  // Suggestion chips
  elements.suggestions.addEventListener("click", (event) => {
    const button = event.target.closest(".suggestion-chip");
    if (!button) return;
    elements.messageInput.value = button.textContent.trim();
    autoResizeTextarea();
    elements.messageInput.focus();
  });

  // Breakdown cards
  document.querySelectorAll(".breakdown-card").forEach((button) => {
    button.addEventListener("click", () => {
      elements.messageInput.value = button.dataset.prompt || "";
      autoResizeTextarea();
      elements.messageInput.focus();
    });
  });
}

/* ============================
   PAGE NAVIGATION
   ============================ */

function showLanding() {
  elements.landingPage.classList.remove("hidden");
  elements.mainApp.classList.add("hidden");
  // Reset to hero view
  elements.landingHero.classList.remove("hidden");
  elements.intakeChat.classList.add("hidden");
  elements.landingFooter.classList.remove("hidden");
}

function showMainApp() {
  elements.landingPage.classList.add("hidden");
  elements.mainApp.classList.remove("hidden");
  ensureConversationExists();
  renderAll();
}

function skipToApp() {
  state.hasEnteredApp = true;
  saveState();
  showMainApp();
  elements.messageInput.focus();
}

function goBackToLanding() {
  showLanding();
}

/* ============================
   INTAKE FLOW
   ============================ */

async function startIntake() {
  // Switch landing page from hero to intake chat
  elements.landingHero.classList.add("hidden");
  elements.landingFooter.classList.add("hidden");
  elements.intakeChat.classList.remove("hidden");
  elements.intakeMessages.innerHTML = "";

  // Call the backend to get the greeting
  try {
    elements.intakeStatus.textContent = "Starting intake...";
    const response = await fetch(API.intake, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    if (!response.ok) throw new Error("Failed to start intake");

    const data = await response.json();
    state.intakeSessionId = data.intake_session_id;
    saveState();

    appendIntakeMessage("assistant", data.response);
    updateIntakeProgress(data.step_number, data.total_steps, data.step_label);
    elements.intakeStatus.textContent = "Ready";
    elements.intakeInput.focus();
  } catch {
    appendIntakeMessage("assistant",
      "Hi! I'll help you create your intake form. " +
      "Let's start — what's the main reason for your visit today?"
    );
    elements.intakeStatus.textContent = "Offline mode";
    elements.intakeInput.focus();
  }
}

async function handleIntakeSend() {
  const text = elements.intakeInput.value.trim();
  if (!text || intakeInFlight) return;

  appendIntakeMessage("user", text);
  elements.intakeInput.value = "";
  elements.intakeInput.style.height = "auto";

  intakeInFlight = true;
  elements.intakeStatus.textContent = "Processing...";

  // Show typing indicator
  const typingEl = appendIntakeMessage("typing", "");

  try {
    const response = await fetch(API.intake, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        intake_session_id: state.intakeSessionId,
        message: text,
      }),
    });

    if (!response.ok) throw new Error("Intake request failed");

    const data = await response.json();
    state.intakeSessionId = data.intake_session_id;
    saveState();

    // Remove typing indicator
    typingEl.remove();

    // Handle emergency
    if (data.emergency) {
      appendIntakeMessage("emergency", data.response);
    } else {
      appendIntakeMessage("assistant", data.response);
    }

    updateIntakeProgress(data.step_number, data.total_steps, data.step_label);

    // If intake is complete, show the transition
    if (data.intake_complete) {
      state.intakeForm = data.intake_form;
      state.hasEnteredApp = true;
      saveState();

      // Show "Continue to assistant" button after a short delay
      setTimeout(() => {
        const btn = document.createElement("button");
        btn.className = "landing-cta intake-continue-btn";
        btn.textContent = "Continue to assistant";
        btn.addEventListener("click", () => {
          showMainApp();
          elements.messageInput.focus();
        });
        elements.intakeMessages.appendChild(btn);
        scrollIntakeToBottom();
      }, 500);
    }

    elements.intakeStatus.textContent = data.intake_complete ? "Intake complete" : "Ready";
  } catch {
    typingEl.remove();
    appendIntakeMessage("assistant", "Something went wrong. Please try again.");
    elements.intakeStatus.textContent = "Error";
  } finally {
    intakeInFlight = false;
    elements.intakeInput.focus();
  }
}

function appendIntakeMessage(role, text) {
  const el = document.createElement("div");

  if (role === "typing") {
    el.className = "intake-message assistant";
    el.innerHTML = `
      <div class="intake-avatar">AI</div>
      <div class="intake-bubble typing-bubble">
        <span>Thinking</span>
        <span class="typing-dots"><span></span><span></span><span></span></span>
      </div>
    `;
  } else if (role === "emergency") {
    el.className = "intake-message emergency";
    el.innerHTML = `
      <div class="intake-avatar" style="background: var(--danger); border-color: var(--danger);">!</div>
      <div class="intake-bubble intake-emergency-bubble">${renderParagraphs(text)}</div>
    `;
  } else {
    el.className = `intake-message ${role}`;
    const avatar = role === "user" ? "You" : "AI";
    el.innerHTML = `
      <div class="intake-avatar">${avatar}</div>
      <div class="intake-bubble">${renderParagraphs(text)}</div>
    `;
  }

  elements.intakeMessages.appendChild(el);
  scrollIntakeToBottom();
  return el;
}

function updateIntakeProgress(stepNum, totalSteps, stepLabel) {
  const pct = Math.round((stepNum / totalSteps) * 100);
  elements.intakeProgressFill.style.width = `${pct}%`;
  elements.intakeStepLabel.textContent = `Step ${stepNum} of ${totalSteps} — ${stepLabel}`;
}

function scrollIntakeToBottom() {
  elements.intakeMessages.scrollTop = elements.intakeMessages.scrollHeight;
}

/* ============================
   STATE
   ============================ */

function loadState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return {
      conversations: [],
      currentConversationId: null,
      uploadedFile: null,
      hasEnteredApp: false,
      intakeSessionId: null,
      intakeForm: null,
    };
  }

  try {
    return JSON.parse(raw);
  } catch {
    return {
      conversations: [],
      currentConversationId: null,
      uploadedFile: null,
      hasEnteredApp: false,
      intakeSessionId: null,
      intakeForm: null,
    };
  }
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

/* ============================
   CONVERSATIONS
   ============================ */

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

function deleteConversation(id) {
  state.conversations = state.conversations.filter((c) => c.id !== id);

  if (state.currentConversationId === id) {
    if (state.conversations.length) {
      state.currentConversationId = state.conversations[0].id;
    } else {
      const convo = makeConversation("New conversation");
      state.conversations.unshift(convo);
      state.currentConversationId = convo.id;
    }
  }

  saveState();
  renderAll();
}

/* ============================
   REVIEW PANEL & FILES
   ============================ */

function toggleReviewPanel() {
  elements.reviewPanel.classList.toggle("force-open");
}

function scrollMessagesToBottom() {
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
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

  if (!backendOnline) {
    await checkBackendHealth();
  }

  if (!backendOnline) return;

  const formData = new FormData();
  formData.append("file", file);

  try {
    elements.composerStatus.textContent = "Uploading document...";
    const response = await fetch(API.upload, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) throw new Error("Upload failed");

    const data = await response.json();

    state.uploadedFile = {
      ...state.uploadedFile,
      serverId: data.document_id || null,
      summary: data.summary || null,
    };

    saveState();
    renderFileCard();
    elements.composerStatus.textContent = "Document uploaded";

    // Start a new conversation about the document
    const convo = makeConversation(file.name);
    state.conversations.unshift(convo);
    state.currentConversationId = convo.id;

    const prompt = `I just uploaded a medical document: "${file.name}". Please explain the important parts of this document in simple, plain language.`;
    elements.messageInput.value = prompt;
    autoResizeTextarea();
    elements.messageInput.focus();
    saveState();
    renderAll();
  } catch {
    elements.composerStatus.textContent = "Upload failed";
  }
}

/* ============================
   BACKEND
   ============================ */

async function checkBackendHealth() {
  try {
    const response = await fetch(API.health, { method: "GET" });
    backendOnline = response.ok;
  } catch {
    backendOnline = false;
  }

  elements.backendStatusText.textContent = backendOnline
    ? "Backend connected"
    : "Backend offline";

  elements.composerStatus.textContent = backendOnline ? "Ready" : "Waiting for backend";
}

/* ============================
   SEND MESSAGE
   ============================ */

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
      throw new Error("Backend is not available. Start your Flask app.");
    }

    elements.composerStatus.textContent = "Fetching answer...";

    const response = await fetch(API.chat, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
      text: error.message || "Something went wrong.",
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

/* ============================
   RENDERING
   ============================ */

function renderAll() {
  renderConversationList();
  renderMessages();
  renderFileCard();
}

function renderConversationList() {
  elements.conversationList.innerHTML = "";

  state.conversations.forEach((conversation) => {
    const item = document.createElement("div");
    item.className = `conversation-item ${conversation.id === state.currentConversationId ? "active" : ""}`;

    const messageCount = conversation.messages.filter((m) => m.role !== "typing").length;
    const dateLabel = formatRelativeDate(conversation.createdAt);

    const content = document.createElement("div");
    content.className = "conversation-item-content";
    content.innerHTML = `
      <div class="conversation-title">${escapeHtml(conversation.title)}</div>
      <div class="conversation-meta">
        <span>${dateLabel}</span>
        <span>${messageCount} msg</span>
      </div>
    `;

    content.addEventListener("click", () => switchConversation(conversation.id));

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "delete-convo-btn";
    deleteBtn.title = "Delete conversation";
    deleteBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>`;
    deleteBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteConversation(conversation.id);
    });

    item.appendChild(content);
    item.appendChild(deleteBtn);
    elements.conversationList.appendChild(item);
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
      <div class="mini-label">Getting started</div>
      <p>
        Describe your symptoms, ask a health question, or upload a medical document
        for a plain-language explanation. Answers include cited sources from our medical database.
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

  const avatarLabel = message.role === "user" ? "You" : "AI";
  const authorLabel = message.role === "user" ? "You" : "MedAssist";

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
        <span>MedAssist</span>
        <span>${formatTime(message.timestamp)}</span>
      </div>
      <div class="bubble typing-bubble">
        <span>Thinking</span>
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
          <div class="source-score">Relevance: ${escapeHtml(source.score)}</div>
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
    <p class="file-meta">${escapeHtml(state.uploadedFile.type)} &middot; ${state.uploadedFile.size}</p>
    <p class="file-meta">Uploaded ${formatRelativeDate(state.uploadedFile.uploadedAt)}</p>
    ${state.uploadedFile.summary ? `<p class="file-meta">${escapeHtml(state.uploadedFile.summary)}</p>` : ""}
  `;
}

/* ============================
   UTILITIES
   ============================ */

function autoResizeTextarea() {
  const textarea = elements.messageInput;
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
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

  return date.toLocaleDateString([], { month: "short", day: "numeric" });
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
