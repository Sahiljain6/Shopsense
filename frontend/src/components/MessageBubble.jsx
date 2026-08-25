import { motion } from "framer-motion";
import ProductCard from "./ProductCard";
import MarkdownRenderer from "./MarkdownRenderer";

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";
  const products = Array.isArray(message.products) ? message.products : [];

  return (
    <motion.div
      className={`message-group ${isUser ? "user-group" : "assistant-group"}`}
      initial={{ opacity: 0, y: 16, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      <div className="message-header-meta">
        <span className="role-avatar-badge">
          {isUser ? "👤 You" : "✨ ShopSense AI"}
        </span>
      </div>

      <div className={`message-bubble ${isUser ? "user" : "assistant"}`}>
        {isUser ? (
          <p className="user-message-text">{message.text || ""}</p>
        ) : (
          <MarkdownRenderer content={message.text || ""} />
        )}
      </div>

      {message.response?.clarification && (
        <div className="clarification-banner">
          <span className="clarification-icon">💡</span>
          <div className="clarification-text">
            <strong>Note from Assistant:</strong> {message.response.clarification}
          </div>
        </div>
      )}

      {products.length > 0 && (
        <div className="product-results-section">
          <div className="product-results-header">
            <span className="results-count-badge">
              🛍️ {products.length} {products.length === 1 ? "Product Match" : "Product Matches Found"}
            </span>
          </div>
          <div className="product-grid">
            {products.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                response={message.response}
              />
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
