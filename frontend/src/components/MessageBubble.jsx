import { motion } from "framer-motion";
import ProductCard from "./ProductCard";

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";
  const products = Array.isArray(message.products) ? message.products : [];

  return (
    <motion.div
      className="message-group"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className={`message-bubble ${isUser ? "user" : "assistant"}`}>
        <p>{message.text || "Couldn't display this message."}</p>
      </div>

      {message.response?.clarification && (
        <div className="alert alert-warning">
          {message.response.clarification}
        </div>
      )}

      {products.length > 0 && (
        <div className="product-grid">
          {products.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              response={message.response}
            />
          ))}
        </div>
      )}
    </motion.div>
  );
}
