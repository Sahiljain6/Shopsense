import { motion } from "framer-motion";
import ProductCard from "./ProductCard";
import MarkdownRenderer from "./MarkdownRenderer";

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";
  const products = Array.isArray(message.products) ? message.products : [];

  return (
    <div className={`chat-message-row ${isUser ? "user-row" : "assistant-row"}`}>
      <div className="message-avatar-box">
        {isUser ? (
          <div className="avatar-circle user-avatar">
            <span>M</span>
          </div>
        ) : (
          <div className="avatar-circle ai-avatar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4 7H20L18.5 17H5.5L4 7Z" stroke="#ffffff" strokeWidth="2.2"/>
              <path d="M9 7V5C9 3.89543 9.89543 3 11 3H13C14.1046 3 15 3.89543 15 5V7" stroke="#ffffff" strokeWidth="2.2"/>
            </svg>
          </div>
        )}
      </div>

      <div className="message-content-box">
        <div className="message-sender-name">
          {isUser ? "You" : "ShopSense AI"}
        </div>

        <div className={`message-bubble-body ${isUser ? "user-bubble" : "assistant-bubble"}`}>
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
    </div>
  );
}
