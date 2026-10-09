import { useState, useRef, useEffect, useCallback } from "react";
import MessageBubble from "./MessageBubble";
import WelcomePromptGrid from "./WelcomePromptGrid";
import AttachmentPreviewBar from "./AttachmentPreviewBar";
import ComposerInput from "./ComposerInput";
import TypingIndicator from "./TypingIndicator";
import { streamChat, sendChat, fetchLink, identifyImage, friendlyError, getToken } from "../api";
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

export default function ChatPanel({ onError, onClearError, isLoggedIn = false, onOpenAuth }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState(null);
  const [isWarmingUp, setIsWarmingUp] = useState(false);
  const [attachedFile, setAttachedFile] = useState(null);
  const [selectedModel, setSelectedModel] = useState("Sonnet 4.5");
  const [showScrollBottom, setShowScrollBottom] = useState(false);

  const containerRef = useRef(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const warmUpTimerRef = useRef(null);
  const abortControllerRef = useRef(null);
  const isNearBottomRef = useRef(true);
  const tokenBatchTimerRef = useRef(null);

  // Monitor scroll position without layout thrashing
  const handleScroll = useCallback((e) => {
    const el = e.currentTarget;
    if (!el) return;
    const isBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    isNearBottomRef.current = isBottom;
    setShowScrollBottom(!isBottom && messages.length > 2);
  }, [messages.length]);

  // Efficient instant or smooth scroll
  const scrollToBottom = useCallback((smooth = false) => {
    const el = containerRef.current;
    if (!el) return;
    if (smooth) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    } else {
      el.scrollTop = el.scrollHeight;
    }
    isNearBottomRef.current = true;
    setShowScrollBottom(false);
  }, []);

  // Stick to bottom during streaming ONLY if user hasn't scrolled up
  useEffect(() => {
    if (isNearBottomRef.current) {
      scrollToBottom(false);
    }
  }, [messages, loading, scrollToBottom]);

  // Cleanup timers & ongoing streams on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (warmUpTimerRef.current) {
        clearTimeout(warmUpTimerRef.current);
      }
      if (tokenBatchTimerRef.current) {
        clearTimeout(tokenBatchTimerRef.current);
      }
    };
  }, []);

  const removeAttachment = useCallback(() => {
    setAttachedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const executeSend = useCallback(
    async (textToSend) => {
      const hasAuth = isLoggedIn || Boolean(getToken());
      if (!hasAuth) {
        if (onOpenAuth) {
          onOpenAuth("signin");
        }
        return;
      }

      const file = attachedFile;
      const text = (textToSend || "").trim();
      if (!file && !text) return;

      onClearError();

      // ── LOCAL INTERCEPTS (zero backend overhead) ──
      const lowered = text.toLowerCase().trim();

      // Cart query
      if (!file && CART_QUERIES.some((q) => lowered === q || lowered.includes("my cart") || lowered.includes("in cart"))) {
        setMessages((prev) => [
          ...prev,
          { role: "user", text },
          { role: "assistant", text: buildCartResponse() },
        ]);
        return;
      }

      // Greeting
      if (!file && GREETING_QUERIES.includes(lowered)) {
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

      // Photo upload flow
      if (file) {
        setMessages((prev) => [...prev, { role: "user", text: `Uploaded: ${file.name}` }]);
        setAttachedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
        try {
          const response = await identifyImage(file);
          // Directly use products array returned in response - zero second request!
          const products = Array.isArray(response.products) && response.products.length
            ? response.products
            : [];
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              text: response.answer || "Here's what I found from your photo.",
              response,
              products
            }
          ]);
        } catch (err) {
          onError(friendlyError(err));
        } finally {
          setLoading(false);
        }
        return;
      }

      // URL scrape flow
      if (URL_PATTERN.test(text)) {
        setMessages((prev) => [...prev, { role: "user", text: `🔗 ${text}` }]);
        try {
          const result = await fetchLink(text);
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              text: `**${result.created ? "Added" : "Synced"}**: ${result.product.name}\nPrice: **₹${Number(result.product.price).toLocaleString("en-IN")}**`,
              response: {},
              products: [result.product],
            }
          ]);
        } catch (err) {
          onError(friendlyError(err));
        } finally {
          setLoading(false);
        }
        return;
      }

      // ── REAL SSE STREAMING CHAT FLOW ──
      setIsWarmingUp(false);
      setLoadingStatus("Thinking...");
      if (warmUpTimerRef.current) clearTimeout(warmUpTimerRef.current);
      warmUpTimerRef.current = setTimeout(() => {
        setIsWarmingUp(true);
      }, 7000);

      const history = messages.slice(-8).map((m) => ({
        role: m.role === "user" ? "user" : "assistant",
        content: m.text,
      }));

      // Cancel any previous active stream
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      // 1. Immediately render user message
      // 2. Immediately render assistant placeholder for instant feedback
      setMessages((prev) => [
        ...prev,
        { role: "user", text },
        {
          role: "assistant",
          text: "",
          streaming: true,
          model: selectedModel,
          products: [],
        },
      ]);

      // Token batching buffer to eliminate React state update storms
      let accumulatedText = "";
      let tokenBatchBuffer = "";

      // Limit full Markdown + message-tree updates to about 30 FPS while
      // buffering all tokens. Completion flushes the remaining text immediately.
      const flushTokenBatch = () => {
        tokenBatchTimerRef.current = null;
        if (!tokenBatchBuffer) return;

        accumulatedText += tokenBatchBuffer;
        tokenBatchBuffer = "";
        setMessages((prev) => {
          const next = [...prev];
          const lastIdx = next.length - 1;
          if (lastIdx >= 0 && next[lastIdx].role === "assistant") {
            next[lastIdx] = {
              ...next[lastIdx],
              text: accumulatedText,
            };
          }
          return next;
        });
      };

      const handleToken = (token) => {
        tokenBatchBuffer += token;
        if (!tokenBatchTimerRef.current) {
          tokenBatchTimerRef.current = setTimeout(flushTokenBatch, 32);
        }
      };

      try {
        await streamChat({
          message: text,
          mode: null,
          history,
          cart: getCart(),
          model: selectedModel,
          signal: controller.signal,
          onStatus: (status) => {
            setLoadingStatus(status);
          },
          onToken: handleToken,
          onProducts: (products, product_ids) => {
            setMessages((prev) => {
              const next = [...prev];
              const lastIdx = next.length - 1;
              if (lastIdx >= 0 && next[lastIdx].role === "assistant") {
                next[lastIdx] = {
                  ...next[lastIdx],
                  products: products || [],
                  product_ids: product_ids || [],
                };
              }
              return next;
            });
          },
          onComplete: (fullText, fullMeta) => {
            if (tokenBatchTimerRef.current) {
              clearTimeout(tokenBatchTimerRef.current);
              tokenBatchTimerRef.current = null;
            }
            accumulatedText += tokenBatchBuffer;
            tokenBatchBuffer = "";
            const finalText = fullText || accumulatedText;
            setMessages((prev) => {
              const next = [...prev];
              const lastIdx = next.length - 1;
              if (lastIdx >= 0 && next[lastIdx].role === "assistant") {
                next[lastIdx] = {
                  ...next[lastIdx],
                  text: finalText || "Here is what I found:",
                  streaming: false,
                  products: fullMeta?.products || next[lastIdx].products || [],
                  response: fullMeta || {},
                  model: fullMeta?.model || selectedModel,
                };
              }
              return next;
            });
          },
          onError: async (streamErr) => {
            if (streamErr.name === "AbortError") return;
            // Graceful fallback to standard /chat endpoint if stream is interrupted
            try {
              const fallbackResp = await sendChat(
                text,
                null,
                history,
                getCart(),
                (status) => {
                  if (status === "waking") setIsWarmingUp(true);
                },
                selectedModel
              );
              const prods = Array.isArray(fallbackResp.products) ? fallbackResp.products : [];
              setMessages((prev) => {
                const next = [...prev];
                const lastIdx = next.length - 1;
                if (lastIdx >= 0 && next[lastIdx].role === "assistant") {
                  next[lastIdx] = {
                    ...next[lastIdx],
                    text: fallbackResp.answer || "Here is what I found:",
                    streaming: false,
                    products: prods,
                    response: fallbackResp,
                    model: fallbackResp.model || selectedModel,
                  };
                }
                return next;
              });
            } catch (fallbackErr) {
              onError(friendlyError(fallbackErr));
            }
          },
        });
      } catch (err) {
        if (err.name !== "AbortError") {
          onError(friendlyError(err));
        }
      } finally {
        if (tokenBatchTimerRef.current) {
          clearTimeout(tokenBatchTimerRef.current);
          tokenBatchTimerRef.current = null;
        }
        if (warmUpTimerRef.current) clearTimeout(warmUpTimerRef.current);
        setLoading(false);
        setIsWarmingUp(false);
        setLoadingStatus(null);
      }
    },
    [isLoggedIn, onOpenAuth, attachedFile, messages, selectedModel, onClearError, onError]
  );

  return (
    <div className="chatbot-widget-container">
      {/* Messages */}
      <div
        ref={containerRef}
        className="chatbot-messages-stream"
        onScroll={handleScroll}
      >
        {messages.length === 0 && !loading ? (
          <WelcomePromptGrid onSelectPrompt={executeSend} />
        ) : (
          <>
            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}
            {loading && (
              <TypingIndicator
                isWarmingUp={isWarmingUp}
                status={loadingStatus || "Thinking..."}
              />
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Floating Jump to Latest Button */}
      {showScrollBottom && (
        <button
          type="button"
          className="jump-to-latest-btn"
          onClick={() => scrollToBottom(true)}
          title="Jump to latest messages"
          aria-label="Jump to latest messages"
          style={{
            position: "absolute",
            bottom: "80px",
            right: "24px",
            zIndex: 30,
            background: "rgba(15, 23, 42, 0.9)",
            border: "1px solid rgba(6, 182, 212, 0.4)",
            color: "#67e8f9",
            borderRadius: "9999px",
            padding: "0.4rem 0.85rem",
            fontSize: "0.78rem",
            fontWeight: 600,
            boxShadow: "0 4px 16px rgba(0, 0, 0, 0.4)",
            cursor: "pointer",
          }}
        >
          ↓ Jump to latest
        </button>
      )}

      {/* Attachment bar */}
      <AttachmentPreviewBar attachedFile={attachedFile} onRemove={removeAttachment} />

      {/* Composer Card with isolated typing state */}
      <ComposerInput
        isLoggedIn={isLoggedIn}
        onOpenAuth={onOpenAuth}
        attachedFile={attachedFile}
        fileInputRef={fileInputRef}
        onAttachFile={(e) => setAttachedFile(e.target.files[0] || null)}
        onRemoveAttachment={removeAttachment}
        selectedModel={selectedModel}
        onSelectModel={setSelectedModel}
        onSendMessage={executeSend}
        loading={loading}
      />
    </div>
  );
}
