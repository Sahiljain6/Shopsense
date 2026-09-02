import { motion } from "framer-motion";
import ModelDropdown from "./ModelDropdown";

export default function ComposerInput({
  isLoggedIn,
  onOpenAuth,
  inputText,
  setInputText,
  attachedFile,
  fileInputRef,
  onAttachFile,
  onRemoveAttachment,
  selectedModel,
  onSelectModel,
  onSubmit,
  hasContent,
  loading,
}) {
  return (
    <form className="chatbot-composer fastshot-composer-card" onSubmit={onSubmit}>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={onAttachFile}
      />

      <div
        className="composer-main-row"
        onClick={!isLoggedIn && onOpenAuth ? () => onOpenAuth("signin") : undefined}
        style={!isLoggedIn ? { cursor: "pointer" } : undefined}
      >
        <input
          className="composer-text-input"
          type="text"
          placeholder={
            isLoggedIn
              ? "Ask about products, compare prices, check EMI..."
              : "Sign in to chat, compare prices & find deals..."
          }
          autoComplete="off"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          disabled={!isLoggedIn || Boolean(attachedFile)}
          aria-label={isLoggedIn ? "Chat input" : "Log in to use chat"}
        />

        <div className="composer-action-cluster">
          <ModelDropdown
            selectedModel={selectedModel}
            onSelectModel={onSelectModel}
          />

          <button
            type="button"
            className="composer-attach-btn"
            onClick={(e) => {
              if (!isLoggedIn) {
                e.stopPropagation();
                onOpenAuth?.("signin");
                return;
              }
              attachedFile ? onRemoveAttachment() : fileInputRef.current?.click();
            }}
            title={attachedFile ? "Remove photo" : "Attach product photo"}
            aria-label="Attach photo"
          >
            {attachedFile ? (
              <span className="attach-check">✓</span>
            ) : (
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l7.88-7.87" />
              </svg>
            )}
          </button>

          <motion.button
            type="submit"
            className="composer-fastshot-send"
            whileTap={{ scale: 0.92 }}
            disabled={!isLoggedIn || !hasContent || loading}
            aria-label="Send message"
          >
            {loading ? (
              <span className="send-spinner">●</span>
            ) : (
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#ffffff"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M5 12h14" />
                <path d="m12 5 7 7-7 7" />
              </svg>
            )}
          </motion.button>
        </div>
      </div>
    </form>
  );
}
