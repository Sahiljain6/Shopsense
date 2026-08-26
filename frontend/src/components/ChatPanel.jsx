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

export default function ChatPanel({ onError, onClearError }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Hello! 👋 I'm ShopSense, your AI shopping assistant. What products or deals are you looking for today?",
    },
  ]);
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

  const executeSend = useCallback(
    async (textToSend) => {
      const file = attachedFile;
      const text = (textToSend !== undefined ? textToSend : inputText).trim();

      if (!file && !text) return;

      onClearError();
      setLoading(true);

      // Photo Analysis Flow
      if (file) {
        setMessages((prev) => [
          ...prev,
          { role: "user", text: `Uploaded photo: ${file.name}` },
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

      // Link Fetch Flow
      if (URL_PATTERN.test(text)) {
        setInputText("");
        setMessages((prev) => [
          ...prev,
          { role: "user", text: `Product link: ${text}` },
        ]);

        try {
          const result = await fetchLink(text);
          const label = result.created ? "Added to catalog" : "Live Price Synced";
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              text: `**${label}**: [${result.product.name}](${text})\n\nPrice: **₹${Number(result.product.price).toLocaleString('en-IN')}**`,
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

      // Chat Flow
      setInputText("");
      setMessages((prev) => {
        const history = prev.slice(-8).map((m) => ({
          role: m.role === "user" ? "user" : "assistant",
          content: m.text,
        }));
        const next = [...prev, { role: "user", text }];

        (async () => {
          try {
            const response = await sendChat(text, null, history);
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
                text: response.answer || "Here are my top recommendations based on your criteria:",
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
      {/* Blue Widget Header (Matching Image 2) */}
      <div className="chatbot-widget-header">
        <div className="widget-header-left">
          <div className="widget-logo-box">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4 7H20L18.5 17H5.5L4 7Z" stroke="#ffffff" strokeWidth="2.2"/>
              <path d="M9 7V5C9 3.89543 9.89543 3 11 3H13C14.1046 3 15 3.89543 15 5V7" stroke="#ffffff" strokeWidth="2.2"/>
            </svg>
          </div>
          <div className="widget-header-title">
            <span className="widget-title">ShopSense</span>
            <span className="widget-subtitle">AI Assistant</span>
          </div>
        </div>

        <div className="widget-controls">
          <span className="control-btn" title="Minimize">—</span>
          <span className="control-btn" title="Maximize">□</span>
          <span className="control-btn" title="Close">✕</span>
        </div>
      </div>

      {/* Chat Messages Stream */}
      <div className="chatbot-messages-stream">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {loading && (
          <div className="chat-typing-row">
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Attachment Tray */}
      <AnimatePresence>
        {attachedFile && (
          <motion.div
            className="chat-attachment-bar"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
          >
            <span>📷 {attachedFile.name}</span>
            <button type="button" onClick={removeAttachment}>✕</button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Composer Input Dock (Matching Image 2) */}
      <form className="chatbot-composer" onSubmit={handleSubmit}>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleFileChange}
        />

        <button
          type="button"
          className="composer-icon-btn"
          title="Attach product link or photo"
          onClick={handleAttachClick}
        >
          📎
        </button>

        <input
          className="composer-text-input"
          type="text"
          placeholder="Type your query here..."
          autoComplete="off"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          disabled={Boolean(attachedFile)}
        />

        <button
          type="button"
          className="composer-icon-btn"
          title="Emoji"
          onClick={() => setInputText((prev) => prev + " 😊")}
        >
          😊
        </button>

        <button
          type="submit"
          className="composer-send-circle-btn"
          disabled={loading || !hasContent}
          title="Send query"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M4 7H20L18.5 17H5.5L4 7Z" stroke="#ffffff" strokeWidth="2.2"/>
            <path d="M9 7V5C9 3.89543 9.89543 3 11 3H13C14.1046 3 15 3.89543 15 5V7" stroke="#ffffff" strokeWidth="2.2"/>
          </svg>
        </button>
      </form>
    </div>
  );
}
