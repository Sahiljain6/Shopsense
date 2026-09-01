import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import MessageBubble from "./MessageBubble";
import ModelDropdown from "./ModelDropdown";
import QuickActionsToolbar from "./QuickActionsToolbar";
import { sendChat, fetchLink, getProducts, identifyImage, friendlyError } from "../api";
import { getCartFromStorage } from "../hooks/useCart";

const CART_QUERIES = [
  "show my cart", "view cart", "open cart", "cart",
  "what is in my cart", "cart items", "my cart",
];

const GREETING_QUERIES = [
  "hi", "hello", "hey", "hola", "namaste", "good morning", "good evening", "help",
];

const URL_PATTERN = /^https?:\/\/[^\s]+$/;

function getCart() {
  return getCartFromStorage();
}

function buildCartResponse() {
  const items = getCart();
  if (items.length === 0) {
    return "🛒 **Your cart is empty.**\n\nAsk me to recommend products and click **Add to Cart** to get started!";
  }
  const total = items.reduce((sum, item) => sum + (item.price || 0) * (item.qty || 1), 0);
  const lines = items
    .map((item) => `• **${item.name}** × ${item.qty || 1} — ₹${Number((item.price || 0) * (item.qty || 1)).toLocaleString("en-IN")}`)
    .join("\n");
  return `🛒 **Your Cart (${items.length} item${items.length === 1 ? "" : "s"}):**\n\n${lines}\n\n**Total: ₹${Number(total).toLocaleString("en-IN")}**\n\nClick the **🛒 Cart** icon in the top right to review and proceed to checkout!`;
}

export default function ChatPanel({ onError, onClearError, isLoggedIn = false }) {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [isWarmingUp, setIsWarmingUp] = useState(false);
  const [attachedFile, setAttachedFile] = useState(null);
  const [selectedModel, setSelectedModel] = useState("Sonnet 4.5");
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
              },
              selectedModel
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
              response,
              products,
              model: response.model || selectedModel,
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
          <div className="chat-welcome-state fastshot-welcome-card">
            <div className="welcome-brand-mark">
              <svg width="32" height="32" viewBox="0 0 34 34">
                <circle cx="17" cy="17" r="17" fill="#9C86CE"/>
                <circle cx="17" cy="17" r="8.6" fill="#FFFFFF"/>
                <circle cx="17" cy="17" r="3.7" fill="#151519"/>
              </svg>
            </div>
            <h3 className="welcome-title">Describe a product. We'll find the best deal.</h3>
            <p className="welcome-desc">ShopSense AI connects live pricing, verified specs, EMI calculations, and delivery checks across India.</p>
            
            <div className="welcome-chips fastshot-prompts-grid">
              {[
                { icon: "🎧", title: "Best Earbuds", query: "Best wireless earbuds with ANC under ₹3,000" },
                { icon: "📱", title: "Compare Phones", query: "Compare iPhone 15 vs OnePlus 12 specs and value" },
                { icon: "⌨️", title: "Mechanical Keyboard", query: "Top gaming mechanical keyboard under ₹4,000" },
                { icon: "💳", title: "EMI Breakdown", query: "Calculate EMI for ₹50,000 laptop for 6 months at 14%" }
              ].map((item) => (
                <button
                  key={item.title}
                  type="button"
                  className="welcome-chip fastshot-hero-chip"
                  onClick={() => executeSend(item.query)}
                >
                  <span className="hero-chip-icon">{item.icon}</span>
                  <div className="hero-chip-text">
                    <span className="hero-chip-title">{item.title}</span>
                    <span className="hero-chip-sub">{item.query}</span>
                  </div>
                </button>
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
      <QuickActionsToolbar onSelectAction={executeSend} />

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
            <ModelDropdown
              selectedModel={selectedModel}
              onSelectModel={setSelectedModel}
            />

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
