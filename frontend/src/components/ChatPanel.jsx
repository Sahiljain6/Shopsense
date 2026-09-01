import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import MessageBubble from "./MessageBubble";
import QuickActionsToolbar from "./QuickActionsToolbar";
import WelcomePromptGrid from "./WelcomePromptGrid";
import AttachmentPreviewBar from "./AttachmentPreviewBar";
import ComposerInput from "./ComposerInput";
import { sendChat, fetchLink, getProducts, identifyImage, friendlyError } from "../api";
import { getCartFromStorage } from "../hooks/useCart";
import { CART_QUERIES, GREETING_QUERIES, URL_PATTERN } from "../utils/constants";

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
          <WelcomePromptGrid onSelectPrompt={executeSend} />
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
      <AttachmentPreviewBar attachedFile={attachedFile} onRemove={removeAttachment} />

      {/* Fastshot Quick Actions Toolbar */}
      <QuickActionsToolbar onSelectAction={executeSend} />

      {/* Composer Card */}
      <ComposerInput
        isLoggedIn={isLoggedIn}
        inputText={inputText}
        setInputText={setInputText}
        attachedFile={attachedFile}
        fileInputRef={fileInputRef}
        onAttachFile={(e) => setAttachedFile(e.target.files[0] || null)}
        onRemoveAttachment={removeAttachment}
        selectedModel={selectedModel}
        onSelectModel={setSelectedModel}
        onSubmit={handleSubmit}
        hasContent={hasContent}
        loading={loading}
      />
    </div>
  );
}
