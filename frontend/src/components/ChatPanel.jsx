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

const MODES = [
  {
    id: "compare",
    label: "Compare Specs",
    icon: "⚖️",
    badge: "BENCHMARK",
    desc: "Side-by-side spec comparison, pros/cons, & value breakdown",
    placeholder: "Enter 2+ products to benchmark (e.g. iPhone 15 Pro vs Galaxy S24 Ultra)...",
    suggestions: [
      "iPhone 15 Pro vs Samsung S24 Ultra",
      "Sony WH-1000XM5 vs Bose QC Ultra",
      "MacBook Air M3 vs Dell XPS 13",
    ],
  },
  {
    id: "budget_optimizer",
    label: "Budget Cap",
    icon: "💰",
    badge: "PRICE LIMIT",
    desc: "Maximize performance-to-price ratio within your exact budget ceiling",
    placeholder: "Set target budget (e.g. Best noise-cancelling headphones under $100)...",
    suggestions: [
      "Best wireless earbuds under $50",
      "Gaming laptops under $800",
      "4K Smart TVs under $400",
    ],
  },
  {
    id: "gift_mode",
    label: "Gift Finder",
    icon: "🎁",
    badge: "CURATED",
    desc: "Personalized gift suggestions based on recipient profile & budget",
    placeholder: "Who is the gift for? (e.g. Tech gift for gamer under $75)...",
    suggestions: [
      "Tech gift for photographer under $100",
      "Gift for coffee enthusiast under $50",
      "Ergonomic workspace gifts",
    ],
  },
  {
    id: "quick_answer",
    label: "Quick Verdict",
    icon: "⚡",
    badge: "INSTANT",
    desc: "Fast, no-fluff buying recommendation & deal sanity check",
    placeholder: "Ask any buying question (e.g. Is iPhone 15 worth it in 2026?)...",
    suggestions: [
      "Is M3 MacBook Air worth buying today?",
      "OLED vs QLED: Which should I choose?",
      "Best value iPad for students",
    ],
  },
];

// Curated live preview products to give visual commerce feel immediately
const SHOWCASE_PRODUCTS = [
  {
    name: "Sony WH-1000XM5 Noise Cancelling",
    category: "Audio",
    price: "$328.00",
    oldPrice: "$399.99",
    savings: "18% OFF",
    rating: "4.8 ★",
    prompt: "Show me deals and review summary for Sony WH-1000XM5",
  },
  {
    name: "Apple MacBook Air 13\" M3",
    category: "Laptops",
    price: "$999.00",
    oldPrice: "$1,099.00",
    savings: "$100 OFF",
    rating: "4.9 ★",
    prompt: "Compare MacBook Air M3 with M2 model",
  },
  {
    name: "Samsung Galaxy S24 Ultra 5G",
    category: "Smartphones",
    price: "$1,149.00",
    oldPrice: "$1,299.99",
    savings: "$150 OFF",
    rating: "4.7 ★",
    prompt: "Compare Galaxy S24 Ultra with iPhone 15 Pro",
  },
];

const DEFAULT_SUGGESTIONS = [
  "Find top wireless earbuds under $100",
  "Compare iPhone 15 and Samsung Galaxy S24",
  "Recommend a mechanical gaming keyboard",
  "Top 4K Smart TVs with OLED display",
];

const URL_PATTERN = /^https?:\/\/\S+$/i;

export default function ChatPanel({ onError, onClearError }) {
  const [messages, setMessages] = useState([]);
  const [mode, setMode] = useState(null);
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [attachedFile, setAttachedFile] = useState(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const activeModeConfig = MODES.find((m) => m.id === mode);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, scrollToBottom]);

  const handleModeToggle = useCallback((modeId) => {
    setMode((prev) => (prev === modeId ? null : modeId));
  }, []);

  const removeAttachment = useCallback(() => {
    setAttachedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const handleFileChange = useCallback((e) => {
    setAttachedFile(e.target.files[0] || null);
  }, []);

  const handleAttachClick = useCallback(() => {
    if (attachedFile) {
      removeAttachment();
      return;
    }
    fileInputRef.current?.click();
  }, [attachedFile, removeAttachment]);

  const handleSuggestionClick = useCallback((suggestion) => {
    setInputText(suggestion);
  }, []);

  const executeSend = useCallback(
    async (textToSend, fileToSend) => {
      const file = fileToSend || attachedFile;
      const text = (textToSend !== undefined ? textToSend : inputText).trim();

      if (!file && !text) return;

      onClearError();
      setLoading(true);

      // 1. Photo Analysis Flow
      if (file) {
        setMessages((prev) => [
          ...prev,
          { role: "user", text: `📸 Analyzed image: ${file.name}` },
        ]);
        setAttachedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";

        try {
          const response = await identifyImage(file);
          const ids = Array.isArray(response.product_ids) ? response.product_ids : [];
          const catalog = ids.length ? await getProducts("", 20) : [];
          const products = ids.length ? catalog.filter((p) => ids.includes(p.id)) : [];
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              text: response.answer || "Here is what I detected from your image.",
              response,
              products,
            },
          ]);
        } catch (err) {
          onError(friendlyError(err));
        } finally {
          setLoading(false);
        }
        return;
      }

      // 2. Direct Scraper / URL Fetch Flow
      if (URL_PATTERN.test(text)) {
        setInputText("");
        setMessages((prev) => [
          ...prev,
          { role: "user", text: `🔗 Fetching product link: ${text}` },
        ]);

        try {
          const result = await fetchLink(text);
          const label = result.created ? "Catalog Added" : "Live Price Synced";
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              text: `**${label}**: [${result.product.name}](${text})\n\nCaptured at **${result.product.currency || "$"}${result.product.price}**. Price tracking & deal monitoring are active.`,
              response: {},
              products: [result.product],
            },
          ]);
        } catch (err) {
          onError(friendlyError(err));
        } finally {
          setLoading(false);
        }
        return;
      }

      // 3. AI Shopping Conversation Flow
      setInputText("");
      setMessages((prev) => {
        const history = prev.slice(-8).map((m) => ({
          role: m.role === "user" ? "user" : "assistant",
          content: m.text,
        }));
        const next = [...prev, { role: "user", text }];

        (async () => {
          try {
            const response = await sendChat(text, mode, history);
            const ids = Array.isArray(response.product_ids) ? response.product_ids : [];
            const catalog = ids.length ? await getProducts(text, 12) : [];
            const fallbackCatalog =
              ids.length && !catalog.some((p) => ids.includes(p.id))
                ? await getProducts("", 12)
                : catalog;
            const products = ids.length ? fallbackCatalog.filter((p) => ids.includes(p.id)) : [];
            setMessages((prev2) => [
              ...prev2,
              {
                role: "assistant",
                text: response.answer || "Here are the top matches based on your request.",
                response,
                products,
              },
            ]);
          } catch (err) {
            onError(friendlyError(err));
          } finally {
            setLoading(false);
          }
        })();

        return next;
      });
    },
    [attachedFile, inputText, mode, onClearError, onError]
  );

  const handleSubmit = (e) => {
    e.preventDefault();
    if (loading) return;
    executeSend();
  };

  const currentSuggestions = activeModeConfig ? activeModeConfig.suggestions : DEFAULT_SUGGESTIONS;
  const hasContent = Boolean(inputText.trim()) || Boolean(attachedFile);

  return (
    <section className="chat-panel-commerce" aria-live="polite">
      {/* ── 1. TACTILE SHOPPING MODES (Clear visual hierarchy) ── */}
      <div className="mode-deck">
        <div className="mode-deck-header">
          <span className="deck-title">SHOPPING MODES</span>
          <span className="deck-sub">Click a mode to focus recommendations</span>
        </div>

        <div className="mode-cards-grid">
          {MODES.map((m) => {
            const isActive = mode === m.id;
            return (
              <motion.button
                key={m.id}
                className={`mode-card ${isActive ? "active" : ""}`}
                type="button"
                onClick={() => handleModeToggle(m.id)}
                whileHover={{ y: -2, scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <div className="mode-card-top">
                  <span className="mode-card-icon">{m.icon}</span>
                  <span className="mode-card-badge">{m.badge}</span>
                </div>
                <span className="mode-card-label">{m.label}</span>
              </motion.button>
            );
          })}
        </div>

        {/* Active mode description banner */}
        <AnimatePresence>
          {activeModeConfig && (
            <motion.div
              className="active-mode-indicator"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
            >
              <div className="active-mode-content">
                <span className="active-tag">{activeModeConfig.icon} {activeModeConfig.label} Active:</span>
                <span className="active-desc">{activeModeConfig.desc}</span>
              </div>
              <button
                type="button"
                className="clear-mode-btn"
                onClick={() => setMode(null)}
                title="Reset to all categories"
              >
                ✕ Reset
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── 2. MESSAGES VIEWPORT ── */}
      <div className="messages-stream">
        {messages.length === 0 && !loading ? (
          <div className="commerce-empty-state">
            {/* Live visual product preview showcase */}
            <div className="showcase-header">
              <span className="showcase-badge">TRENDING DEALS & BENCHMARKS</span>
              <p className="showcase-title">Click any item below to compare live prices, or type below:</p>
            </div>

            <div className="showcase-cards-row">
              {SHOWCASE_PRODUCTS.map((prod, idx) => (
                <div
                  key={idx}
                  className="showcase-card"
                  onClick={() => executeSend(prod.prompt)}
                  title={`Ask about ${prod.name}`}
                >
                  <div className="showcase-top">
                    <span className="showcase-category">{prod.category}</span>
                    <span className="showcase-discount">{prod.savings}</span>
                  </div>
                  <h4 className="showcase-name">{prod.name}</h4>
                  <div className="showcase-meta">
                    <div className="showcase-pricing">
                      <span className="price-current">{prod.price}</span>
                      <span className="price-old">{prod.oldPrice}</span>
                    </div>
                    <span className="showcase-rating">{prod.rating}</span>
                  </div>
                  <span className="showcase-action">Analyze Deal ➔</span>
                </div>
              ))}
            </div>

            {/* Understated prompt ideas */}
            <div className="smart-prompts-container">
              <span className="prompts-label">Or try asking:</span>
              <div className="prompts-list">
                {currentSuggestions.map((prompt, i) => (
                  <button
                    key={i}
                    type="button"
                    className="ghost-prompt-btn"
                    onClick={() => handleSuggestionClick(prompt)}
                  >
                    <span>{prompt}</span>
                    <span className="prompt-arrow">➔</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}
            <AnimatePresence>
              {loading && (
                <motion.div
                  className="commerce-typing-card"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                >
                  <div className="typing-pulse-beacon" />
                  <span className="typing-msg">Querying price history & verified catalog...</span>
                </motion.div>
              )}
            </AnimatePresence>
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* ── 3. SUGGESTION BAR (In-session) ── */}
      {messages.length > 0 && !loading && (
        <div className="inchat-prompts-bar">
          <span className="inchat-title">Suggested:</span>
          {currentSuggestions.slice(0, 3).map((prompt, i) => (
            <button
              key={i}
              type="button"
              className="inchat-chip"
              onClick={() => handleSuggestionClick(prompt)}
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      {/* ── 4. ATTACHMENT TRAY ── */}
      <AnimatePresence>
        {attachedFile && (
          <motion.div
            className="attachment-tray"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 6 }}
          >
            <span className="tray-icon">📷</span>
            <span className="tray-filename">{attachedFile.name}</span>
            <button
              type="button"
              className="tray-remove"
              onClick={removeAttachment}
              aria-label="Remove photo"
            >
              ✕
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── 5. PRECISION COMPOSER DOCK ── */}
      <form className="composer-dock" onSubmit={handleSubmit}>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleFileChange}
        />
        <motion.button
          className={`dock-btn attach-btn ${attachedFile ? "active" : ""}`}
          type="button"
          title="Upload or snap photo of product"
          aria-label="Attach photo"
          onClick={handleAttachClick}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          {attachedFile ? "✓" : "📷"}
        </motion.button>

        <input
          className="dock-input"
          type="text"
          placeholder={activeModeConfig ? activeModeConfig.placeholder : "Ask about products, compare models, paste a link, or attach a photo..."}
          autoComplete="off"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          disabled={Boolean(attachedFile)}
        />

        <motion.button
          className="dock-btn send-btn"
          type="submit"
          disabled={loading || !hasContent}
          whileHover={!loading && hasContent ? { scale: 1.03 } : {}}
          whileTap={!loading && hasContent ? { scale: 0.97 } : {}}
        >
          {loading ? (
            <span className="dock-spinner" />
          ) : (
            <span className="dock-send-icon">➔</span>
          )}
          <span>{loading ? "Searching..." : "Ask Copilot"}</span>
        </motion.button>
      </form>
    </section>
  );
}
