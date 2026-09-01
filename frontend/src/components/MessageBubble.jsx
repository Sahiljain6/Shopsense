import { useState } from "react";
import { motion } from "framer-motion";
import ProductCard from "./ProductCard";
import MarkdownRenderer from "./MarkdownRenderer";

export default function MessageBubble({ message }) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";
  const products = Array.isArray(message.products) ? message.products : [];

  const handleCopy = () => {
    if (message.text) {
      navigator.clipboard.writeText(message.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <motion.div
      className={`chat-message-row ${isUser ? "user-row" : "assistant-row"}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="message-avatar-box">
        {isUser ? (
          <div className="avatar-circle user-avatar">
            <span>Y</span>
          </div>
        ) : (
          <div className="avatar-circle ai-avatar fastshot-avatar" title="ShopSense AI Engine">
            <svg width="20" height="20" viewBox="0 0 34 34">
              <circle cx="17" cy="17" r="17" fill="#9C86CE"/>
              <circle cx="17" cy="17" r="8.6" fill="#FFFFFF"/>
              <circle cx="17" cy="17" r="3.7" fill="#151519"/>
            </svg>
          </div>
        )}
      </div>

      <div className="message-content-box">
        <div className="message-header-row">
          <span className="message-sender-name">
            {isUser ? "You" : "ShopSense AI"}
          </span>
          {!isUser && (
            <div className="message-actions-cluster">
              <span className="message-model-tag">Sonnet 4.5</span>
              <button
                type="button"
                className="message-copy-btn"
                onClick={handleCopy}
                title="Copy response to clipboard"
                aria-label="Copy response"
              >
                {copied ? "✓ Copied" : "📋 Copy"}
              </button>
            </div>
          )}
        </div>

        <div className={`message-bubble-body ${isUser ? "user-bubble fastshot-user-bubble" : "assistant-bubble fastshot-assistant-bubble"}`}>
          {isUser ? (
            <p className="user-text-content">{message.text || ""}</p>
          ) : (
            <MarkdownRenderer content={message.text || ""} />
          )}
        </div>

        {products.length > 0 && (
          <div className="message-product-cards-grid">
            {products.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                response={message.response}
              />
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}
