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
  { id: "compare", label: "Compare" },
  { id: "budget_optimizer", label: "Budget" },
  { id: "gift_mode", label: "Gift" },
  { id: "quick_answer", label: "Quick answer" },
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

  const handleSubmit = useCallback(
    async (e) => {
      e.preventDefault();
      if (loading) return;

      const file = attachedFile;
      const text = inputText.trim();
      if (!file && !text) return;

      onClearError();
      setLoading(true);

      if (file) {
        setMessages((prev) => [
          ...prev,
          { role: "user", text: `Uploaded image: ${file.name}` },
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
              text: response.answer || "Here's what I found.",
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

      if (URL_PATTERN.test(text)) {
        setInputText("");
        setMessages((prev) => [
          ...prev,
          { role: "user", text: `Fetch link: ${text}` },
        ]);

        try {
          const result = await fetchLink(text);
          const label = result.created ? "Added to catalog" : "Price updated in catalog";
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              text: `${label}: ${result.product.name}`,
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
                text: response.answer || "I found a few options.",
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
    [attachedFile, inputText, loading, mode, onClearError, onError]
  );

  const hasContent = Boolean(inputText.trim()) || Boolean(attachedFile);

  return (
    <section className="chat-panel" aria-live="polite">
      <div className="mode-buttons">
        {MODES.map((m) => (
          <motion.button
            key={m.id}
            className={`mode-button ${mode === m.id ? "active" : ""}`}
            type="button"
            onClick={() => handleModeToggle(m.id)}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            layout
          >
            {m.label}
          </motion.button>
        ))}
      </div>

      <div className="messages">
        {messages.length === 0 && !loading ? (
          <div className="empty-state">
            Ask a question, paste a product link, or attach a photo.
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}
            <AnimatePresence>
              {loading && (
                <motion.div
                  className="typing"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-label">ShopSense is typing</span>
                </motion.div>
              )}
            </AnimatePresence>
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      <AnimatePresence>
        {attachedFile && (
          <motion.div
            className="attachment-preview"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
          >
            <span className="attachment-chip">
              📷 {attachedFile.name}
              <button
                type="button"
                onClick={removeAttachment}
                aria-label="Remove photo"
              >
                ✕
              </button>
            </span>
          </motion.div>
        )}
      </AnimatePresence>

      <form className="chat-form" onSubmit={handleSubmit}>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleFileChange}
        />
        <motion.button
          className={`attach-button ${attachedFile ? "active" : ""}`}
          type="button"
          title="Attach a photo"
          aria-label="Attach a photo"
          onClick={handleAttachClick}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
        >
          📎
        </motion.button>
        <input
          className="chat-input"
          type="text"
          placeholder="Ask, paste a product link, or attach a photo…"
          autoComplete="off"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          disabled={Boolean(attachedFile)}
        />
        <motion.button
          className="primary-button send-button"
          type="submit"
          disabled={loading || !hasContent}
          whileHover={!loading && hasContent ? { scale: 1.05 } : {}}
          whileTap={!loading && hasContent ? { scale: 0.95 } : {}}
        >
          {loading ? "Sending…" : "Send"}
        </motion.button>
      </form>
    </section>
  );
}
