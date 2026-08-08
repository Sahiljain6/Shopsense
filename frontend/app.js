const API_URL = window.SHOPSENSE_API_URL || "http://localhost:8000";
const TOKEN_KEY = "shopsense_token";
const PROTECTED_PATHS = ["/chat", "/compare", "/reviews/summary", "/history", "/wishlist"];
const MODES = [
  { id: "compare", label: "Compare" },
  { id: "budget_optimizer", label: "Budget" },
  { id: "gift_mode", label: "Gift" },
  { id: "quick_answer", label: "Quick answer" },
];

const state = {
  authed: Boolean(localStorage.getItem(TOKEN_KEY)),
  isRegister: false,
  authLoading: false,
  chatLoading: false,
  mode: null,
  messages: [],
};

const elements = {
  logoutButton: document.getElementById("logout-button"),
  error: document.getElementById("error"),
  authCard: document.getElementById("auth-card"),
  authTitle: document.getElementById("auth-title"),
  authForm: document.getElementById("auth-form"),
  fullName: document.getElementById("full-name"),
  email: document.getElementById("email"),
  password: document.getElementById("password"),
  authSubmit: document.getElementById("auth-submit"),
  toggleAuth: document.getElementById("toggle-auth"),
  chatPanel: document.getElementById("chat-panel"),
  modeButtons: document.getElementById("mode-buttons"),
  messages: document.getElementById("messages"),
  chatForm: document.getElementById("chat-form"),
  chatInput: document.getElementById("chat-input"),
  chatSubmit: document.getElementById("chat-submit"),
};

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
}

function setError(message) {
  elements.error.textContent = message || "";
  elements.error.classList.toggle("hidden", !message);
}

function friendlyError(error) {
  if (error instanceof ApiError) {
    return error.status === 401 ? "401: Session expired. Please log in again." : `${error.status}: ${error.message}`;
  }
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

async function responseMessage(response) {
  const text = await response.text();
  if (!text) return response.statusText || "Request failed";
  try {
    const data = JSON.parse(text);
    return data.detail || data.message || text;
  } catch {
    return text;
  }
}

async function apiFetch(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const token = localStorage.getItem(TOKEN_KEY);
  if (token && PROTECTED_PATHS.some((protectedPath) => path.startsWith(protectedPath))) {
    headers.Authorization = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`${API_URL}${path}`, { ...options, headers, signal: controller.signal });
    if (!response.ok) throw new ApiError(response.status, await responseMessage(response));
    return response.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(408, "The request timed out after 15 seconds. Please try again.");
    }
    throw new ApiError(0, error instanceof Error ? error.message : "Network request failed. Please try again.");
  } finally {
    clearTimeout(timeoutId);
  }
}

const login = (payload) => apiFetch("/auth/login", { method: "POST", body: JSON.stringify(payload) });
async function register(payload) {
  await apiFetch("/auth/register", { method: "POST", body: JSON.stringify(payload) });
  return login({ email: payload.email, password: payload.password });
}
const sendChat = (message, mode) => apiFetch("/chat", { method: "POST", body: JSON.stringify({ message, mode }) });
const getProducts = (q = "", limit = 8) => apiFetch(`/products?q=${encodeURIComponent(q)}&limit=${limit}`);

function renderProductCard(product, response) {
  const key = String(product.id);
  const pros = Array.isArray(response?.pros?.[key]) ? response.pros[key] : [];
  const cons = Array.isArray(response?.cons?.[key]) ? response.cons[key] : [];
  return `<article class="product-card">
    ${product.image_url ? `<img src="${escapeHtml(product.image_url)}" alt="" class="product-image" loading="lazy" />` : ""}
    <div class="product-body">
      <div><p class="product-brand">${escapeHtml(product.brand || product.category_name || "ShopSense")}</p><h3>${escapeHtml(product.name || "Recommended product")}</h3></div>
      <p class="product-description">${escapeHtml(product.description || "No description available.")}</p>
      <div class="product-meta"><span>${escapeHtml(product.currency || "$")}${escapeHtml(product.price)}</span><span class="rating">★ ${escapeHtml(product.rating || "N/A")}</span></div>
      ${response?.reasons?.[key] ? `<p class="reason">${escapeHtml(response.reasons[key])}</p>` : ""}
      ${pros.length ? `<p class="pros">Pros: ${escapeHtml(pros.join(", "))}</p>` : ""}
      ${cons.length ? `<p class="cons">Cons: ${escapeHtml(cons.join(", "))}</p>` : ""}
    </div>
  </article>`;
}

function renderMessages() {
  if (!state.messages.length && !state.chatLoading) {
    elements.messages.innerHTML = '<div class="empty-state">Try “recommend a budget phone under 15000”.</div>';
    return;
  }
  elements.messages.innerHTML = state.messages.map((message) => {
    const products = Array.isArray(message.products) ? message.products : [];
    return `<div class="message-group"><div class="message-bubble ${message.role === "user" ? "user" : "assistant"}"><p>${escapeHtml(message.text || "Couldn’t display this message.")}</p></div>
      ${message.response?.clarification ? `<div class="alert alert-warning">${escapeHtml(message.response.clarification)}</div>` : ""}
      ${products.length ? `<div class="product-grid">${products.map((product) => renderProductCard(product, message.response)).join("")}</div>` : ""}</div>`;
  }).join("") + (state.chatLoading ? '<div class="typing">ShopSense is typing…</div>' : "");
  elements.messages.scrollTop = elements.messages.scrollHeight;
}

function render() {
  elements.logoutButton.classList.toggle("hidden", !state.authed);
  elements.authCard.classList.toggle("hidden", state.authed);
  elements.chatPanel.classList.toggle("hidden", !state.authed);
  elements.authTitle.textContent = state.isRegister ? "Create your account" : "Log in to continue";
  elements.fullName.classList.toggle("hidden", !state.isRegister);
  elements.authSubmit.textContent = state.authLoading ? "Please wait…" : state.isRegister ? "Register" : "Log in";
  elements.authSubmit.disabled = state.authLoading;
  elements.toggleAuth.textContent = state.isRegister ? "Already have an account? Log in" : "Need an account? Register";
  elements.modeButtons.innerHTML = MODES.map((item) => `<button class="mode-button ${state.mode === item.id ? "active" : ""}" type="button" data-mode="${item.id}">${item.label}</button>`).join("");
  elements.chatSubmit.textContent = state.chatLoading ? "Sending…" : "Send";
  elements.chatSubmit.disabled = state.chatLoading || !elements.chatInput.value.trim();
  renderMessages();
}

async function handleAuth(event) {
  event.preventDefault();
  setError(null);
  state.authLoading = true;
  render();
  try {
    const payload = { email: elements.email.value, password: elements.password.value };
    if (state.isRegister && elements.fullName.value) payload.full_name = elements.fullName.value;
    const token = state.isRegister ? await register(payload) : await login(payload);
    localStorage.setItem(TOKEN_KEY, token.access_token);
    state.authed = true;
  } catch (error) {
    setError(friendlyError(error));
  } finally {
    state.authLoading = false;
    render();
  }
}

async function handleChat(event) {
  event.preventDefault();
  const text = elements.chatInput.value.trim();
  if (!text || state.chatLoading) return;
  elements.chatInput.value = "";
  setError(null);
  state.chatLoading = true;
  state.messages.push({ role: "user", text });
  render();
  try {
    const response = await sendChat(text, state.mode);
    const ids = Array.isArray(response.product_ids) ? response.product_ids : [];
    const products = ids.length ? (await getProducts(text, 12)).filter((product) => ids.includes(product.id)) : [];
    state.messages.push({ role: "assistant", text: response.answer || "I found a few options.", response, products });
  } catch (error) {
    setError(friendlyError(error));
  } finally {
    state.chatLoading = false;
    render();
  }
}

elements.authForm.addEventListener("submit", handleAuth);
elements.chatForm.addEventListener("submit", handleChat);
elements.chatInput.addEventListener("input", render);
elements.toggleAuth.addEventListener("click", () => { state.isRegister = !state.isRegister; setError(null); render(); });
elements.logoutButton.addEventListener("click", () => { localStorage.removeItem(TOKEN_KEY); state.authed = false; state.messages = []; setError(null); render(); });
elements.modeButtons.addEventListener("click", (event) => {
  const button = event.target.closest("[data-mode]");
  if (!button) return;
  state.mode = state.mode === button.dataset.mode ? null : button.dataset.mode;
  render();
});

render();
