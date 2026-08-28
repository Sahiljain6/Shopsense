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

export default function ChatPanel({ onError, onClearError }) {
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

      {/* Composer */}
      <form className="chatbot-composer" onSubmit={handleSubmit}>
        <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={(e) => setAttachedFile(e.target.files[0] || null)} />
        <button type="button" className="composer-icon-btn" onClick={() => attachedFile ? removeAttachment() : fileInputRef.current?.click()}>
          {attachedFile ? "✓" : "📎"}
        </button>
        <input
          className="composer-text-input"
          type="text"
          placeholder="Ask about products, compare prices, check your cart..."
          autoComplete="off"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          disabled={Boolean(attachedFile)}
        />
        <button type="submit" className="composer-send-circle-btn" disabled={loading || !hasContent}>
          {loading ? "..." : "➤"}
        </button>
      </form>
    </div>
  );
}
