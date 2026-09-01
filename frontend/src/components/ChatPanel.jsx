import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  sendChat,
  fetchLink,
  identifyImage,
  getProducts,
  friendlyError,
} from "../api";
import MessageBubble from "./MessageBubble";

const URL_PATTERN = /^https?:\/\/\S+$/i;
const CART_KEY = "shopsense_cart";

// Local queries that should NOT go to backend
const CART_QUERIES = ["cart", "my cart", "whats in my cart", "what's in my cart", "show cart", "show my cart", "cart items"];
const GREETING_QUERIES = ["hi", "hello", "hey", "help", "hi there", "hello there"];

function getCart() {
  try { return JSON.parse(localStorage.getItem(CART_KEY) || "[]"); } catch { return []; }
}

function buildCartResponse() {
  const cart = getCart();
  if (cart.length === 0) {
    return "Your cart is empty! 🛒\n\nTry asking me for product recommendations and click **Add to Cart** on any product you like.";
  }
  const total = cart.reduce((s, i) => s + (i.price || 0) * (i.qty || 1), 0);
  let msg = "### 🛒 Your Cart\n\n";
  cart.forEach((item, idx) => {
    msg += `${idx + 1}. **${item.name}** — ₹${Number(item.price).toLocaleString("en-IN")} × ${item.qty} = **₹${Number(item.price * item.qty).toLocaleString("en-IN")}**\n`;
  });
  msg += `\n---\n**Total: ₹${Number(total).toLocaleString("en-IN")}**\n\n💡 *Click the 🛒 cart icon in the top bar to manage items or checkout.*`;
  return msg;
}

export default function ChatPanel({ onError, onClearError, isLoggedIn = false }) {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [isWarmingUp, setIsWarmingUp] = useState(false);
  const [attachedFile, setAttachedFile] = useState(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const warmUpTimerRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, loading, scrollToBottom]);

  const removeAttachment = useCallback(() => {
    setAttachedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const executeSend = useCallback(
    async (textToSend) => {
      const file = attachedFile;
      const text = (textToSend !== undefined ? textToSend : inputText).trim();
      if (!file && !text) return;

      onClearError();

      // ── LOCAL INTERCEPTS (no backend call needed) ──
      const lowered = text.toLowerCase().trim();

      // Cart query
      if (!file && CART_QUERIES.some((q) => lowered === q || lowered.includes("my cart") || lowered.includes("in cart"))) {
        setInputText("");
        setMessages((prev) => [
          ...prev,
          { role: "user", text },
          { role: "assistant", text: buildCartResponse() },
        ]);
        return;
      }

      // Greeting
      if (!file && GREETING_QUERIES.includes(lowered)) {
        setInputText("");
        setMessages((prev) => [
          ...prev,
          { role: "user", text },
          {
            role: "assistant",
            text: "Hello! 👋 I'm **ShopSense**, your AI shopping assistant for India.\n\nI can help you:\n• 🔍 Find products by category or budget\n• ⚖️ Compare specs side-by-side\n• 💰 Find the best deals on Amazon, Flipkart & Croma\n• 🏷️ Check ongoing offers & coupon codes\n\n**Try asking:** *\"Best earbuds under ₹2,000\"* or *\"Compare iPhone 15 vs OnePlus 12\"*",
          },
        ]);
        return;
      }

      setLoading(true);

      // Photo flow
      if (file) {
        setMessages((prev) => [...prev, { role: "user", text: `Uploaded: ${file.name}` }]);
        setAttachedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
        try {
          const response = await identifyImage(file);
          const ids = Array.isArray(response.product_ids) ? response.product_ids : [];
          const catalog = ids.length ? await getProducts("", 20) : [];
          const products = ids.length ? catalog.filter((p) => ids.includes(p.id)) : [];
          setMessages((prev) => [...prev, { role: "assistant", text: response.answer || "Here's what I found.", response, products }]);
        } catch (err) { onError(friendlyError(err)); }
        finally { setLoading(false); }
        return;
      }

      // URL flow
      if (URL_PATTERN.test(text)) {
        setInputText("");
        setMessages((prev) => [...prev, { role: "user", text: `🔗 ${text}` }]);
        try {
          const result = await fetchLink(text);
          setMessages((prev) => [...prev, {
            role: "assistant",
            text: `**${result.created ? "Added" : "Synced"}**: ${result.product.name}\nPrice: **₹${Number(result.product.price).toLocaleString("en-IN")}**`,
            response: {}, products: [result.product],
          }]);
        } catch (err) { onError(friendlyError(err)); }
        finally { setLoading(false); }
        return;
      }

      // AI chat flow
      setInputText("");
      setIsWarmingUp(false);
      if (warmUpTimerRef.current) clearTimeout(warmUpTimerRef.current);
      warmUpTimerRef.current = setTimeout(() => {
        setIsWarmingUp(true);
      }, 7000);

      setMessages((prev) => {
        const history = prev.slice(-8).map((m) => ({
          role: m.role === "user" ? "user" : "assistant",
          content: m.text,
        }));
        const next = [...prev, { role: "user", text }];

        (async () => {
          try {
            const response = await sendChat(
              text,
              null,
              history,
              getCart(),
              (status) => {
                if (status === "waking") {
                  setIsWarmingUp(true);
                }
              }
            );
            const ids = Array.isArray(response.product_ids) ? response.product_ids : [];
            let products = [];
            if (ids.length > 0) {
              const catalog = await getProducts("", 50);
              products = catalog.filter((p) => ids.includes(p.id));
            }
            setMessages((prev2) => [...prev2, {
              role: "assistant",
              text: response.answer || "Here is what I found:",
              response, products,
            }]);
          } catch (err) { onError(friendlyError(err)); }
          finally {
            if (warmUpTimerRef.current) clearTimeout(warmUpTimerRef.current);
            setLoading(false);
            setIsWarmingUp(false);
          }
        })();

        return next;
      });
    },
    [attachedFile, inputText, onClearError, onError]
  );

  const handleSubmit = (e) => {
    e.preventDefault();
    if (loading) return;
    executeSend();
  };

  const hasContent = Boolean(inputText.trim()) || Boolean(attachedFile);

  return (
    <div className="chatbot-widget-container">
      {/* Blue Header */}
      <div className="chatbot-widget-header">
        <div className="widget-header-left">
          <div className="widget-logo-box">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M4 7H20L18.5 17H5.5L4 7Z" stroke="#fff" strokeWidth="2.2"/>
              <path d="M9 7V5C9 3.89543 9.89543 3 11 3H13C14.1046 3 15 3.89543 15 5V7" stroke="#fff" strokeWidth="2.2"/>
            </svg>
          </div>
          <div className="widget-header-title">
            <span className="widget-title">ShopSense</span>
            <span className="widget-subtitle">AI Assistant</span>
          </div>
        </div>
        <div className="widget-controls">
          <span className="control-btn">—</span>
          <span className="control-btn">□</span>
          <span className="control-btn">✕</span>
        </div>
      </div>

      {/* Messages */}
      <div className="chatbot-messages-stream">
        {messages.length === 0 && !loading ? (
          <div className="chat-welcome-state">
            <div className="welcome-icon">🛍️</div>
            <h3 className="welcome-title">Welcome to ShopSense</h3>
            <p className="welcome-desc">Your AI shopping assistant for India. Ask me anything about products, prices, or deals.</p>
            <div className="welcome-chips">
              {["Best earbuds under ₹2,000", "Compare iPhone 15 vs OnePlus 12", "Gaming keyboard under ₹3,000"].map((q) => (
                <button key={q} type="button" className="welcome-chip" onClick={() => executeSend(q)}>{q}</button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}
            {loading && (
              <div className="chat-typing-container">
                <div className="chat-typing-row">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </div>
                {isWarmingUp && (
                  <div className="chat-warming-notice">
                    <span>⚡</span> Waking up the server, this can take up to a minute...
                  </div>
                )}
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Attachment bar */}
      <AnimatePresence>
        {attachedFile && (
          <motion.div className="chat-attachment-bar" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}>
            <span>📷 {attachedFile.name}</span>
            <button type="button" onClick={removeAttachment}>✕</button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Fastshot Quick Actions Toolbar */}
      <div className="composer-quick-strip" role="toolbar" aria-label="Suggested shopping actions">
        <button type="button" className="fastshot-chip" onClick={() => executeSend("Find best deals on electronics today")}>
          <span className="chip-bullet">⚡</span>
          <span>Today's Deals</span>
        </button>
        <button type="button" className="fastshot-chip" onClick={() => executeSend("Compare iPhone 15 vs OnePlus 12")}>
          <span className="chip-bullet">⚖️</span>
          <span>Compare Specs</span>
        </button>
        <button type="button" className="fastshot-chip" onClick={() => executeSend("Calculate EMI for ₹45,000 for 12 months at 12%")}>
          <span className="chip-bullet">💳</span>
          <span>EMI Calc</span>
        </button>
        <button type="button" className="fastshot-chip" onClick={() => executeSend("Check delivery to pincode 400001")}>
          <span className="chip-bullet">📍</span>
          <span>Pincode Check</span>
        </button>
      </div>

      {/* Composer Card */}
      <form className="chatbot-composer fastshot-composer-card" onSubmit={handleSubmit}>
        <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={(e) => setAttachedFile(e.target.files[0] || null)} />
        
        <div className="composer-main-row">
          <input
            className="composer-text-input"
            type="text"
            placeholder={isLoggedIn ? "Ask about products, compare prices, check EMI..." : "Please log in to chat"}
            autoComplete="off"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={!isLoggedIn || Boolean(attachedFile)}
            aria-label={isLoggedIn ? "Chat input" : "Log in to use chat"}
          />

          <div className="composer-action-cluster">
            <div className="composer-model-pill" title="AI Deal Engine Active">
              <span className="model-dot"></span>
              <span className="model-name">Sonnet 4.5</span>
              <svg className="model-chevron" width="7" height="5" viewBox="0 0 7 5" fill="none">
                <path d="M1 1.5L3.5 3.5L6 1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>

            <button
              type="button"
              className="composer-attach-btn"
              onClick={() => attachedFile ? removeAttachment() : fileInputRef.current?.click()}
              disabled={!isLoggedIn}
              aria-label={isLoggedIn ? "Attach image or screenshot" : "Log in to attach"}
              title="Attach product screenshot or receipt"
            >
              {attachedFile ? (
                <span className="attach-check">✓</span>
              ) : (
                <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
                </svg>
              )}
            </button>

            <motion.button
              type="submit"
              className="composer-fastshot-send"
              disabled={!isLoggedIn || loading || !hasContent}
              whileHover={hasContent ? { scale: 1.06, filter: "brightness(1.08)" } : {}}
              whileTap={hasContent ? { scale: 0.94 } : {}}
              aria-label={isLoggedIn ? "Send message" : "Log in to send messages"}
            >
              {loading ? (
                <span className="send-spinner">...</span>
              ) : (
                <svg width="13" height="13" viewBox="0 0 14 14" fill="currentColor">
                  <path d="M7 1.5L12.5 7L11.2 8.3L7.9 5V12.5H6.1V5L2.8 8.3L1.5 7L7 1.5Z"/>
                </svg>
              )}
            </motion.button>
          </div>
        </div>
      </form>
    </div>
  );
}
