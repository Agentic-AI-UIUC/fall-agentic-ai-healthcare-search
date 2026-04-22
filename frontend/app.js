const STORAGE_KEY = "healthcare_frontend_live_v3";

const API = {
  health: "/api/health",
  chat: "/api/chat",
  upload: "/api/upload",
  preMedical: "/api/pre_medical",
  intake: "/api/intake",
  doctorSession: "/api/doctor/session",
  doctorChat: "/api/doctor/chat",
  doctorQuiz: "/api/doctor/quiz",
  doctorDiff: "/api/doctor/differential",
  authSignup: "/api/auth/signup",
  authLogin: "/api/auth/login",
  authLogout: "/api/auth/logout",
  authMe: "/api/auth/me",
  conversations: "/api/conversations",
};

let currentUser = null;

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
    // Pre-Medical Modal
    preMedicalBtn: document.getElementById("preMedicalBtn"),
    preMedicalModal: document.getElementById("preMedicalModal"),
    closeModalBtn: document.getElementById("closeModalBtn"),
    preMedicalForm: document.getElementById("preMedicalForm"),
    submitFormBtn: document.getElementById("submitFormBtn"),
    formStatus: document.getElementById("formStatus"),
    // Auth
    authModal: document.getElementById("authModal"),
    closeAuthModal: document.getElementById("closeAuthModal"),
    showLoginBtn: document.getElementById("showLoginBtn"),
    showSignupBtn: document.getElementById("showSignupBtn"),
    loginForm: document.getElementById("loginForm"),
    signupForm: document.getElementById("signupForm"),
    loginEmail: document.getElementById("loginEmail"),
    loginPassword: document.getElementById("loginPassword"),
    loginBtn: document.getElementById("loginBtn"),
    loginError: document.getElementById("loginError"),
    signupUsername: document.getElementById("signupUsername"),
    signupEmail: document.getElementById("signupEmail"),
    signupPassword: document.getElementById("signupPassword"),
    signupBtn: document.getElementById("signupBtn"),
    signupError: document.getElementById("signupError"),
    switchToSignup: document.getElementById("switchToSignup"),
    switchToLogin: document.getElementById("switchToLogin"),
    userInfo: document.getElementById("userInfo"),
    userDisplayName: document.getElementById("userDisplayName"),
    logoutBtn: document.getElementById("logoutBtn"),
    // Doctor Practice Mode
    doctorModeToggle: document.getElementById("doctorModeToggle"),
    doctorPanel: document.getElementById("doctorPanel"),
    newCaseBtn: document.getElementById("newCaseBtn"),
    caseCard: document.getElementById("caseCard"),
    caseProgress: document.getElementById("caseProgress"),
    dotHistory: document.getElementById("dotHistory"),
    dotExam: document.getElementById("dotExam"),
    dotLabs: document.getElementById("dotLabs"),
    evaluationCard: document.getElementById("evaluationCard"),
    submitDiagnosisBtn: document.getElementById("submitDiagnosisBtn"),
    diffInput: document.getElementById("diffInput"),
    addDiffBtn: document.getElementById("addDiffBtn"),
    diffList: document.getElementById("diffList"),
    checkDiffBtn: document.getElementById("checkDiffBtn"),
    loadQuizBtn: document.getElementById("loadQuizBtn"),
    quizContainer: document.getElementById("quizContainer"),
  };

  init();
});

async function init() {
  bindEvents();

  // Check if user is already logged in
  await checkAuthStatus();

  if (state.hasEnteredApp && currentUser) {
    showMainApp();
  } else {
    showLanding();
  }

  await checkBackendHealth();
}

function bindEvents() {
  // Auth
  elements.showLoginBtn.addEventListener("click", () => openAuthModal("login"));
  elements.showSignupBtn.addEventListener("click", () => openAuthModal("signup"));
  elements.closeAuthModal.addEventListener("click", closeAuthModalFn);
  elements.switchToSignup.addEventListener("click", (e) => { e.preventDefault(); showAuthForm("signup"); });
  elements.switchToLogin.addEventListener("click", (e) => { e.preventDefault(); showAuthForm("login"); });
  elements.loginBtn.addEventListener("click", handleLogin);
  elements.signupBtn.addEventListener("click", handleSignup);
  elements.logoutBtn.addEventListener("click", handleLogout);

  // Allow Enter key in auth forms
  elements.loginPassword.addEventListener("keydown", (e) => { if (e.key === "Enter") handleLogin(); });
  elements.signupPassword.addEventListener("keydown", (e) => { if (e.key === "Enter") handleSignup(); });

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

  elements.preMedicalBtn.addEventListener("click", () => {
    // Take user back to intake chat to restart conversational intake
    state.hasEnteredApp = false;
    saveState();
    showLanding();
    startIntake();
  });

  elements.closeModalBtn.addEventListener("click", () => {
    elements.preMedicalModal.classList.add("hidden");
  });

  // Doctor Practice Mode
  elements.doctorModeToggle.addEventListener("click", toggleDoctorMode);
  elements.newCaseBtn.addEventListener("click", loadNewCase);

  // Tab switching
  document.querySelectorAll(".doctor-tab").forEach((tab) => {
    tab.addEventListener("click", () => switchDoctorTab(tab.dataset.tab));
  });

  // Quick action chips
  document.querySelectorAll(".doctor-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      elements.messageInput.value = btn.dataset.prompt || "";
      autoResizeTextarea();
      elements.messageInput.focus();
    });
  });

  // Submit diagnosis button
  elements.submitDiagnosisBtn.addEventListener("click", () => {
    elements.messageInput.value = "My diagnosis is: ";
    elements.messageInput.focus();
  });

  // Differential builder
  elements.addDiffBtn.addEventListener("click", addDifferentialHypothesis);
  elements.diffInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); addDifferentialHypothesis(); }
  });
  elements.checkDiffBtn.addEventListener("click", checkDifferentialHypotheses);

  // Quiz
  elements.loadQuizBtn.addEventListener("click", loadQuiz);

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
   AUTH
   ============================ */

async function checkAuthStatus() {
  try {
    const res = await fetch(API.authMe);
    const data = await res.json();
    if (data.user) {
      currentUser = data.user;
      updateAuthUI();
    }
  } catch {
    // not logged in
  }
}

function openAuthModal(mode) {
  elements.authModal.classList.remove("hidden");
  showAuthForm(mode);
}

function closeAuthModalFn() {
  elements.authModal.classList.add("hidden");
  elements.loginError.classList.add("hidden");
  elements.signupError.classList.add("hidden");
}

function showAuthForm(mode) {
  if (mode === "signup") {
    elements.loginForm.classList.add("hidden");
    elements.signupForm.classList.remove("hidden");
  } else {
    elements.signupForm.classList.add("hidden");
    elements.loginForm.classList.remove("hidden");
  }
  elements.loginError.classList.add("hidden");
  elements.signupError.classList.add("hidden");
}

async function handleLogin() {
  const email = elements.loginEmail.value.trim();
  const password = elements.loginPassword.value;

  if (!email || !password) {
    showAuthError("loginError", "Please fill in all fields.");
    return;
  }

  try {
    elements.loginBtn.disabled = true;
    elements.loginBtn.textContent = "Logging in...";
    const res = await fetch(API.authLogin, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      showAuthError("loginError", data.error || "Login failed.");
      return;
    }
    currentUser = data.user;
    updateAuthUI();
    closeAuthModalFn();
    await loadUserConversations();
    state.hasEnteredApp = true;
    saveState();
    showMainApp();
  } catch {
    showAuthError("loginError", "Connection error. Please try again.");
  } finally {
    elements.loginBtn.disabled = false;
    elements.loginBtn.textContent = "Log in";
  }
}

async function handleSignup() {
  const username = elements.signupUsername.value.trim();
  const email = elements.signupEmail.value.trim();
  const password = elements.signupPassword.value;

  if (!username || !email || !password) {
    showAuthError("signupError", "Please fill in all fields.");
    return;
  }
  if (password.length < 6) {
    showAuthError("signupError", "Password must be at least 6 characters.");
    return;
  }

  try {
    elements.signupBtn.disabled = true;
    elements.signupBtn.textContent = "Creating account...";
    const res = await fetch(API.authSignup, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      showAuthError("signupError", data.error || "Signup failed.");
      return;
    }
    currentUser = data.user;
    updateAuthUI();
    closeAuthModalFn();
    state.hasEnteredApp = true;
    saveState();
    showMainApp();
  } catch {
    showAuthError("signupError", "Connection error. Please try again.");
  } finally {
    elements.signupBtn.disabled = false;
    elements.signupBtn.textContent = "Create account";
  }
}

async function handleLogout() {
  try {
    await fetch(API.authLogout, { method: "POST" });
  } catch {
    // proceed with local logout even if request fails
  }
  currentUser = null;
  state.hasEnteredApp = false;
  state.conversations = [];
  state.currentConversationId = null;
  saveState();
  updateAuthUI();
  showLanding();
}

function showAuthError(elementId, message) {
  const el = elements[elementId];
  el.textContent = message;
  el.classList.remove("hidden");
}

function updateAuthUI() {
  if (currentUser) {
    elements.showLoginBtn.classList.add("hidden");
    elements.showSignupBtn.classList.add("hidden");
    elements.skipIntakeBtn.classList.remove("hidden");
    elements.userInfo.classList.remove("hidden");
    elements.userDisplayName.textContent = currentUser.username;
  } else {
    elements.showLoginBtn.classList.remove("hidden");
    elements.showSignupBtn.classList.remove("hidden");
    elements.skipIntakeBtn.classList.add("hidden");
    elements.userInfo.classList.add("hidden");
  }
}

async function loadUserConversations() {
  if (!currentUser) return;
  try {
    const res = await fetch(API.conversations);
    if (!res.ok) return;
    const data = await res.json();
    if (data.conversations && data.conversations.length > 0) {
      state.conversations = data.conversations.map((c) => ({
        id: c.id,
        title: c.title,
        createdAt: c.created_at,
        messages: JSON.parse(c.messages || "[]"),
      }));
      state.currentConversationId = state.conversations[0].id;
      saveState();
    }
  } catch {
    // fall back to local state
  }
}

async function syncConversation(convo) {
  if (!currentUser || !convo) return;
  try {
    await fetch(API.conversations, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: convo.id,
        title: convo.title,
        messages: convo.messages,
      }),
    });
  } catch {
    // silent fail — local state is the source of truth
  }
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
  applyMode();
  renderAll();
}

function skipToApp() {
  if (!currentUser) {
    openAuthModal("login");
    return;
  }
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
  if (!currentUser) {
    openAuthModal("signup");
    return;
  }
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

    appendIntakeMessage("assistant", data.response, data.options);
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
      appendIntakeMessage("assistant", data.response, data.options);
    }

    updateIntakeProgress(data.step_number, data.total_steps, data.step_label);

    // If intake is complete, show download + continue buttons
    if (data.intake_complete) {
      state.intakeForm = data.intake_form;
      state.hasEnteredApp = true;
      saveState();

      setTimeout(() => {
        const actions = document.createElement("div");
        actions.className = "intake-complete-actions";

        const downloadBtn = document.createElement("a");
        downloadBtn.className = "landing-cta-secondary intake-download-btn";
        downloadBtn.href = `/api/intake/${data.intake_session_id}/download`;
        downloadBtn.download = "";
        downloadBtn.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          Download PDF Summary
        `;

        const emailAction = document.createElement("div");
        emailAction.className = "intake-email-row";
        
        const emailInput = document.createElement("input");
        emailInput.type = "email";
        emailInput.placeholder = "doctor@clinic.com";
        
        const emailBtn = document.createElement("button");
        emailBtn.className = "send-email-btn";
        emailBtn.textContent = "Send via App";
        emailBtn.addEventListener("click", async () => {
            const docEmail = emailInput.value.trim();
            if (!docEmail) { emailInput.focus(); return; }
            emailBtn.textContent = "Sending...";
            emailBtn.disabled = true;
            try {
                const res = await fetch(`/api/intake/${data.intake_session_id}/email`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ doctor_email: docEmail })
                });
                const result = await res.json();
                if (res.ok) {
                    emailBtn.textContent = "✓ Sent!";
                    emailBtn.style.background = "var(--success)";
                } else {
                    emailBtn.textContent = "Failed";
                    emailBtn.style.background = "var(--danger)";
                    emailBtn.disabled = false;
                    const errMsg = result.error || "Email failed. Check server logs.";
                    appendIntakeMessage("assistant", errMsg);
                }
            } catch {
                emailBtn.textContent = "Error";
                emailBtn.style.background = "var(--danger)";
                emailBtn.disabled = false;
            }
        });
        
        const mailtoBtn = document.createElement("button");
        mailtoBtn.className = "ghost-btn";
        mailtoBtn.style = "margin-left: 10px; padding: 10px 15px; border-radius: 8px; cursor: pointer; border: 1px solid var(--border);";
        mailtoBtn.textContent = "Open Email App";
        mailtoBtn.title = "Send using your default email client (e.g. Outlook, Apple Mail)";
        mailtoBtn.addEventListener("click", async () => {
            const docEmail = emailInput.value.trim() || "doctor@clinic.com";
            try {
                const res = await fetch(`/api/intake/${data.intake_session_id}/json`);
                if(res.ok) {
                    const jsonRes = await res.json();
                    const form = jsonRes.intake_form;
                    let body = "PATIENT INTAKE SUMMARY\n";
                    body += "======================\n\n";
                    body += `Date: ${form.timestamp || 'N/A'}\n\n`;
                    body += `Reason for Visit: ${form.chief_complaint || 'N/A'}\n`;
                    body += `Demographics: ${form.demographics || 'N/A'}\n`;
                    body += `Emergency/MD: ${form.emergency_contact || 'N/A'}\n`;
                    body += `History: ${form.history || 'N/A'}\n`;
                    body += `Family History: ${form.family_history || 'N/A'}\n`;
                    body += `Lifestyle: ${form.lifestyle || 'N/A'}\n`;
                    body += `Activity: ${form.activity || 'N/A'}\n`;
                    body += `Medications: ${form.medications || 'N/A'}\n`;
                    body += `Objectives: ${form.objectives || 'N/A'}\n`;
                    window.location.href = `mailto:${docEmail}?subject=Patient Intake Summary&body=${encodeURIComponent(body)}`;
                }
            } catch (e) {
                console.error("Failed to construct mailto", e);
            }
        });
        
        emailAction.appendChild(emailInput);
        emailAction.appendChild(emailBtn);
        emailAction.appendChild(mailtoBtn);

        const continueBtn = document.createElement("button");
        continueBtn.className = "landing-cta intake-continue-btn";
        continueBtn.style.marginTop = "15px";
        continueBtn.textContent = "Continue to assistant";
        continueBtn.addEventListener("click", () => {
          skipToApp();
        });

        actions.appendChild(downloadBtn);
        actions.appendChild(emailAction);
        actions.appendChild(continueBtn);
        elements.intakeMessages.appendChild(actions);
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

function appendIntakeMessage(role, text, options = []) {
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
      <div class="intake-bubble">
          ${renderParagraphs(text)}
          <div class="options-mount"></div>
      </div>
    `;
    
    if (options && options.length > 0) {
      const mount = el.querySelector(".options-mount");
      mount.className = "intake-options-container";
      mount.style = "display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px;";
      options.forEach(opt => {
          const btn = document.createElement("button");
          btn.className = "ghost-btn";
          btn.style = "padding: 6px 12px; font-size: 0.9rem; border: 1px solid var(--border); border-radius: 20px; background: var(--surface); color: var(--text); cursor: pointer;";
          btn.textContent = opt;
          btn.addEventListener("click", () => {
              if (opt.toLowerCase().startsWith("other") || opt.toLowerCase() === "yes (please list)") {
                  elements.intakeInput.value = "";
                  elements.intakeInput.focus();
                  elements.intakeInput.placeholder = "Please type your details...";
                  return;
              }
              elements.intakeInput.value = opt;
              handleIntakeSend();
              mount.style.pointerEvents = "none";
              mount.style.opacity = "0.6";
          });
          btn.onmouseover = () => btn.style.background = "var(--border-soft)";
          btn.onmouseout = () => btn.style.background = "var(--surface)";
          mount.appendChild(btn);
      });
    }
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
  const defaults = {
    conversations: [],
    currentConversationId: null,
    uploadedFile: null,
    hasEnteredApp: false,
    intakeSessionId: null,
    intakeForm: null,
    appMode: "patient",
    doctorSessionId: null,
    activeCase: null,
  };

  if (!raw) return defaults;

  try {
    const loaded = JSON.parse(raw);
    return { ...defaults, ...loaded };
  } catch {
    return defaults;
  }
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  // Auto-sync current conversation to server if logged in
  if (currentUser) {
    const convo = getCurrentConversation();
    if (convo) syncConversation(convo);
  }
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
  if (state.appMode === "doctor") {
    return handleDoctorSend();
  }

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

/* ============================
   DOCTOR PRACTICE MODE
   ============================ */

let doctorDifferential = [];

function toggleDoctorMode() {
  state.appMode = state.appMode === "patient" ? "doctor" : "patient";
  saveState();
  applyMode();
}

function applyMode() {
  const isDoctor = state.appMode === "doctor";
  document.body.classList.toggle("doctor-mode", isDoctor);

  elements.doctorModeToggle.textContent = isDoctor ? "Exit Practice" : "Doctor Practice";
  elements.doctorModeToggle.classList.toggle("doctor-mode-active", isDoctor);

  elements.reviewPanel.classList.toggle("hidden", isDoctor);
  elements.doctorPanel.classList.toggle("hidden", !isDoctor);

  elements.messageInput.placeholder = isDoctor
    ? "Ask the patient a question, examine them, order tests, or state your diagnosis..."
    : "Describe your symptoms or ask a medical question...";

  if (isDoctor) {
    renderCaseCard();
    updateProgressDots({});
  }
}

function switchDoctorTab(tabName) {
  document.querySelectorAll(".doctor-tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === tabName));
  document.querySelectorAll(".doctor-tab-content").forEach((c) => c.classList.remove("active"));
  const target = document.getElementById("tab" + tabName.charAt(0).toUpperCase() + tabName.slice(1));
  if (target) target.classList.add("active");
}

async function loadNewCase() {
  elements.newCaseBtn.disabled = true;
  elements.newCaseBtn.textContent = "Loading patient...";
  doctorDifferential = [];
  elements.diffList.innerHTML = "";
  elements.quizContainer.innerHTML = "";
  elements.evaluationCard.innerHTML = `<p class="tab-desc">Submit your diagnosis to unlock results and teaching points.</p>`;

  try {
    const resp = await fetch(API.doctorSession, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    if (!resp.ok) throw new Error("Failed to generate case");

    const data = await resp.json();
    state.doctorSessionId = data.session_id;
    state.activeCase = data.case;
    saveState();

    renderCaseCard();
    updateProgressDots({});
    elements.caseProgress.classList.remove("hidden");
    switchDoctorTab("actions");

    const convo = makeConversation("Doctor Practice Session");
    state.conversations.unshift(convo);
    state.currentConversationId = convo.id;

    convo.messages.push({
      id: crypto.randomUUID(),
      role: "assistant",
      text: data.greeting,
      sources: [],
      timestamp: new Date().toISOString(),
    });

    saveState();
    renderAll();
    scrollMessagesToBottom();
  } catch (err) {
    elements.caseCard.innerHTML = `<div class="case-card-empty" style="color:var(--danger)">Failed to load case. Is the backend running?</div>`;
  } finally {
    elements.newCaseBtn.disabled = false;
    elements.newCaseBtn.textContent = "New Case";
  }
}

async function handleDoctorSend() {
  const text = elements.messageInput.value.trim();
  if (!text || requestInFlight) return;

  if (!state.doctorSessionId) {
    await loadNewCase();
    return;
  }

  const convo = getCurrentConversation();
  if (!convo) return;

  convo.messages.push({ id: crypto.randomUUID(), role: "user", text, timestamp: new Date().toISOString() });
  elements.messageInput.value = "";
  autoResizeTextarea();

  const typingId = crypto.randomUUID();
  convo.messages.push({ id: typingId, role: "typing", timestamp: new Date().toISOString() });

  requestInFlight = true;
  saveState();
  renderMessages();
  scrollMessagesToBottom();

  try {
    const resp = await fetch(API.doctorChat, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.doctorSessionId, message: text }),
    });

    if (!resp.ok) throw new Error(`Backend returned ${resp.status}`);
    const data = await resp.json();

    convo.messages = convo.messages.filter((m) => m.id !== typingId);
    convo.messages.push({
      id: crypto.randomUUID(), role: "assistant",
      text: data.response || "...", sources: [], timestamp: new Date().toISOString(),
    });

    if (data.revealed) updateProgressDots(data.revealed);

    if (data.session_complete && data.evaluation) {
      renderEvaluationCard(data.evaluation);
      switchDoctorTab("teaching");
    }

    elements.composerStatus.textContent = "Ready";
  } catch (err) {
    convo.messages = convo.messages.filter((m) => m.id !== typingId);
    convo.messages.push({
      id: crypto.randomUUID(), role: "error",
      text: err.message || "Something went wrong.", timestamp: new Date().toISOString(),
    });
    elements.composerStatus.textContent = "Request failed";
  } finally {
    requestInFlight = false;
    saveState();
    renderAll();
    scrollMessagesToBottom();
  }
}

// ── Case card & progress ──

function renderCaseCard() {
  if (!state.activeCase) {
    elements.caseCard.innerHTML = `<div class="case-card-empty">Click "New Case" to load a patient.</div>`;
    elements.caseProgress.classList.add("hidden");
    return;
  }

  const d = state.activeCase.difficulty || "beginner";
  const dc = d === "advanced" ? "diff-hard" : d === "intermediate" ? "diff-mid" : "diff-easy";

  elements.caseCard.innerHTML = `
    <div class="case-card-content">
      <div class="case-difficulty ${dc}">${d}</div>
      <p class="case-complaint">"${escapeHtml(state.activeCase.chief_complaint || "Patient loaded")}"</p>
      <p class="case-hint">Ask questions, examine, order tests, then submit your diagnosis.</p>
    </div>
  `;
}

function updateProgressDots(revealed) {
  elements.dotHistory.classList.toggle("revealed", !!revealed.history);
  elements.dotExam.classList.toggle("revealed", !!revealed.exam);
  elements.dotLabs.classList.toggle("revealed", !!revealed.labs);
}

// ── Differential builder ──

function addDifferentialHypothesis() {
  const text = elements.diffInput.value.trim();
  if (!text) return;
  doctorDifferential.push(text);
  elements.diffInput.value = "";
  renderDifferentialList();
}

function renderDifferentialList() {
  elements.diffList.innerHTML = doctorDifferential
    .map((h, i) => `<div class="diff-item" data-index="${i}">
      <span class="diff-text">${escapeHtml(h)}</span>
      <button class="diff-remove" onclick="removeDiff(${i})">x</button>
    </div>`)
    .join("");
}

// expose globally for inline onclick
window.removeDiff = function(i) {
  doctorDifferential.splice(i, 1);
  renderDifferentialList();
};

async function checkDifferentialHypotheses() {
  if (!doctorDifferential.length || !state.doctorSessionId) return;

  elements.checkDiffBtn.disabled = true;
  elements.checkDiffBtn.textContent = "Checking...";

  try {
    const resp = await fetch(API.doctorDiff, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.doctorSessionId, hypotheses: doctorDifferential }),
    });

    if (!resp.ok) throw new Error("Check failed");
    const data = await resp.json();

    elements.diffList.innerHTML = (data.results || [])
      .map((r) => {
        const cls = r.match_level === "correct" ? "diff-correct"
                  : r.match_level === "plausible" ? "diff-plausible" : "diff-unlikely";
        return `<div class="diff-item ${cls}"><span class="diff-text">${escapeHtml(r.hypothesis)}</span><span class="diff-badge">${r.match_level}</span></div>`;
      })
      .join("");
  } catch {
    // silent
  } finally {
    elements.checkDiffBtn.disabled = false;
    elements.checkDiffBtn.textContent = "Check Differential";
  }
}

// ── Quiz ──

async function loadQuiz() {
  if (!state.doctorSessionId) return;

  elements.loadQuizBtn.disabled = true;
  elements.loadQuizBtn.textContent = "Generating...";
  elements.quizContainer.innerHTML = "";

  try {
    const resp = await fetch(API.doctorQuiz, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.doctorSessionId }),
    });

    if (!resp.ok) throw new Error("Quiz failed");
    const data = await resp.json();

    elements.quizContainer.innerHTML = (data.questions || [])
      .map((q, qi) => `
        <div class="quiz-question" data-qi="${qi}" data-answer="${q.answer_index}">
          <p class="quiz-stem">${escapeHtml(q.stem)}</p>
          <div class="quiz-options">
            ${q.options.map((opt, oi) => `
              <button class="quiz-option" data-oi="${oi}" onclick="selectQuizOption(${qi}, ${oi})">
                ${escapeHtml(opt)}
              </button>
            `).join("")}
          </div>
          <p class="quiz-explanation hidden">${escapeHtml(q.explanation || "")}</p>
        </div>
      `)
      .join("");
  } catch {
    elements.quizContainer.innerHTML = `<p class="tab-desc" style="color:var(--danger)">Failed to generate quiz.</p>`;
  } finally {
    elements.loadQuizBtn.disabled = false;
    elements.loadQuizBtn.textContent = "Generate Quiz";
  }
}

window.selectQuizOption = function(qi, oi) {
  const qEl = document.querySelector(`.quiz-question[data-qi="${qi}"]`);
  if (!qEl || qEl.classList.contains("answered")) return;

  qEl.classList.add("answered");
  const correct = parseInt(qEl.dataset.answer);

  qEl.querySelectorAll(".quiz-option").forEach((btn) => {
    const idx = parseInt(btn.dataset.oi);
    btn.disabled = true;
    if (idx === correct) btn.classList.add("quiz-correct");
    if (idx === oi && idx !== correct) btn.classList.add("quiz-wrong");
  });

  const expl = qEl.querySelector(".quiz-explanation");
  if (expl) expl.classList.remove("hidden");
};

// ── Evaluation card (Phase E) ──

function renderEvaluationCard(ev) {
  const correct = ev.diagnosis_correct;
  const grade = ev.overall_grade || (correct ? "A" : "D");
  const gradeColor = { A: "#155724", B: "#155724", C: "#856404", D: "#721c24", F: "#721c24" }[grade] || "#333";

  const identifiedHtml = (ev.key_findings_identified || []).map((f) => `<li>${escapeHtml(f)}</li>`).join("");
  const missedHtml = (ev.missed_findings || []).map((f) => `<li>${escapeHtml(f)}</li>`).join("");
  const diffHtml = (ev.differential || []).map((d) => `<li>${escapeHtml(d)}</li>`).join("");

  elements.evaluationCard.innerHTML = `
    <div class="eval-header ${correct ? 'eval-correct' : 'eval-incorrect'}">
      <span class="eval-grade" style="color:${gradeColor}">${grade}</span>
      <span>${correct ? "Correct diagnosis!" : "Not quite."}</span>
    </div>
    <div class="eval-body">
      <p><strong>Correct diagnosis:</strong> ${escapeHtml(ev.correct_diagnosis || "")}</p>

      ${ev.reasoning_quality ? `<div class="eval-scores">
        <div class="eval-score-item"><span>Reasoning</span><span>${"*".repeat(ev.reasoning_quality)}${"·".repeat(5 - ev.reasoning_quality)}</span></div>
        <div class="eval-score-item"><span>Efficiency</span><span>${"*".repeat(ev.efficiency_score || 3)}${"·".repeat(5 - (ev.efficiency_score || 3))}</span></div>
        ${ev.premature_closure ? '<div class="eval-warn">Premature closure detected</div>' : ''}
      </div>` : ''}

      ${ev.strengths ? `<p><strong>Strengths:</strong> ${escapeHtml(ev.strengths)}</p>` : ''}
      ${ev.improvements ? `<p><strong>To improve:</strong> ${escapeHtml(ev.improvements)}</p>` : ''}

      ${identifiedHtml ? `<p><strong>Findings you identified:</strong></p><ul class="teaching-list">${identifiedHtml}</ul>` : ''}
      ${missedHtml ? `<p><strong>Findings you missed:</strong></p><ul class="teaching-list">${missedHtml}</ul>` : ''}
      ${diffHtml ? `<p><strong>Full differential:</strong></p><ul class="teaching-list">${diffHtml}</ul>` : ''}
    </div>
  `;
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
