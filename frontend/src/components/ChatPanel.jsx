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
    label: "Compare",
    icon: "⚖️",
    desc: "Side-by-side spec comparison, pros/cons, & value breakdown",
    placeholder: "Enter 2+ products to compare (e.g. iPhone 15 Pro vs Galaxy S24 Ultra)...",
    suggestions: [
      "Compare iPhone 15 vs Samsung S24",
      "Sony WH-1000XM5 vs Bose QC Ultra",
      "MacBook Air M3 vs Dell XPS 13",
    ],
  },
  {
    id: "budget_optimizer",
    label: "Budget Optimizer",
    icon: "💰",
    desc: "Maximize price-to-performance within your exact spending limit",
    placeholder: "Tell me your target price (e.g. Best noise-cancelling headphones under $100)...",
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
    desc: "Curated gift recommendations based on personality, age & budget",
    placeholder: "Who are you shopping for? (e.g. Birthday gift for a photographer under $75)...",
    suggestions: [
      "Gift for tech enthusiast under $75",
      "Unique gift for coffee lover",
      "Birthday gift for gamer under $50",
    ],
  },
  {
    id: "quick_answer",
    label: "Quick Answer",
    icon: "⚡",
    desc: "Fast, no-fluff buying verdict & instant deal analysis",
    placeholder: "Ask any quick shopping verdict (e.g. Is iPhone 15 worth buying right now?)...",
    suggestions: [
      "Is M3 MacBook Air worth buying in 2026?",
      "OLED vs QLED: Which should I buy?",
      "Best value iPad for college students",
    ],
  },
];

const DEFAULT_SUGGESTIONS = [
  "Find top wireless earbuds under $100",
  "Compare iPhone 15 and Samsung Galaxy S24",
  "Recommend a mechanical gaming keyboard",
  "Deals on 4K Smart TVs",
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

      // 1. Image Identification Flow
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
              text: response.answer || "Here is what I detected from your photo.",
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

      // 2. Direct URL Fetch Flow
      if (URL_PATTERN.test(text)) {
        setInputText("");
        setMessages((prev) => [
          ...prev,
          { role: "user", text: `🔗 Fetching product: ${text}` },
        ]);

        try {
          const result = await fetchLink(text);
          const label = result.created ? "Added to catalog" : "Live Price Synced";
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              text: `**${label}**: [${result.product.name}](${text})\n\nFound for **${result.product.currency || "$"}${result.product.price}**. Price history tracking has started for this link!`,
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

      // 3. AI Shopping Chat Flow
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
    <section className="chat-panel" aria-live="polite">
      {/* ── TOP 4 FUNCTION MODES ── */}
      <div className="mode-selector-container">
        <div className="mode-selector-label">
          <span className="mode-sparkle">✦</span> AI Shopping Modes
        </div>
        <div className="mode-buttons-row">
          {MODES.map((m) => {
            const isActive = mode === m.id;
            return (
              <motion.button
                key={m.id}
                className={`mode-button ${isActive ? "active" : ""}`}
                type="button"
                onClick={() => handleModeToggle(m.id)}
                whileHover={{ scale: 1.03, y: -2 }}
                whileTap={{ scale: 0.97 }}
                layout
              >
                <span className="mode-icon">{m.icon}</span>
                <span className="mode-title">{m.label}</span>
                {isActive && <span className="mode-active-indicator" />}
              </motion.button>
            );
          })}
        </div>

        {/* Dynamic Mode Helper Pill */}
        <AnimatePresence>
          {activeModeConfig && (
            <motion.div
              className="active-mode-banner"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
            >
              <span className="active-mode-tag">{activeModeConfig.icon} {activeModeConfig.label} Active</span>
              <span className="active-mode-desc">{activeModeConfig.desc}</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── MESSAGES CONTAINER ── */}
      <div className="messages-viewport">
        {messages.length === 0 && !loading ? (
          <div className="empty-state-card">
            <div className="empty-state-icon">🤖</div>
            <h3>How can ShopSense help you shop today?</h3>
            <p>
              Ask for comparisons, find deals by budget, paste an Amazon/Apple link, or attach a photo of any item!
            </p>

            <div className="suggestion-chips-grid">
              <span className="suggestions-headline">Try these smart prompts:</span>
              <div className="chips-list">
                {currentSuggestions.map((prompt, i) => (
                  <button
                    key={i}
                    type="button"
                    className="suggestion-chip"
                    onClick={() => handleSuggestionClick(prompt)}
                  >
                    ✨ {prompt}
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
                  className="typing-indicator-card"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                >
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-text">ShopSense AI is analyzing catalog & live prices...</span>
                </motion.div>
              )}
            </AnimatePresence>
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* ── QUICK SUGGESTION PILLS (When in chat) ── */}
      {messages.length > 0 && !loading && (
        <div className="mini-suggestions-bar">
          <span className="mini-suggestions-title">💡 Quick ideas:</span>
          {currentSuggestions.slice(0, 3).map((prompt, i) => (
            <button
              key={i}
              type="button"
              className="mini-chip"
              onClick={() => handleSuggestionClick(prompt)}
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      {/* ── ATTACHMENT PREVIEW ── */}
      <AnimatePresence>
        {attachedFile && (
          <motion.div
            className="attachment-preview-box"
            initial={{ opacity: 0, scale: 0.9, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 10 }}
          >
            <div className="attachment-chip">
              <span className="attachment-icon">📸</span>
              <span className="attachment-name">{attachedFile.name}</span>
              <button
                type="button"
                className="attachment-remove-btn"
                onClick={removeAttachment}
                aria-label="Remove attached photo"
              >
                ✕
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── FLOATING COMPOSER ── */}
      <form className="chat-composer-form" onSubmit={handleSubmit}>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleFileChange}
        />
        <motion.button
          className={`composer-attach-btn ${attachedFile ? "active" : ""}`}
          type="button"
          title="Upload or snap a photo of any product"
          aria-label="Attach a photo"
          onClick={handleAttachClick}
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.92 }}
        >
          {attachedFile ? "✓" : "📎"}
        </motion.button>

        <input
          className="composer-input"
          type="text"
          placeholder={activeModeConfig ? activeModeConfig.placeholder : "Ask a question, paste a link, or attach a photo..."}
          autoComplete="off"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          disabled={Boolean(attachedFile)}
        />

        <motion.button
          className="composer-send-btn"
          type="submit"
          disabled={loading || !hasContent}
          whileHover={!loading && hasContent ? { scale: 1.05 } : {}}
          whileTap={!loading && hasContent ? { scale: 0.95 } : {}}
        >
          {loading ? (
            <span className="loading-spinner" />
          ) : (
            <span className="send-icon">➤</span>
          )}
          <span>{loading ? "Thinking..." : "Send"}</span>
        </motion.button>
      </form>
    </section>
  );
}
