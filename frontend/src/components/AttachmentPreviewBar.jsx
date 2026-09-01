import { motion, AnimatePresence } from "framer-motion";

export default function AttachmentPreviewBar({ attachedFile, onRemove }) {
  return (
    <AnimatePresence>
      {attachedFile && (
        <motion.div
          className="chat-attachment-bar"
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.15 }}
        >
          <span>📷 {attachedFile.name}</span>
          <button
            type="button"
            onClick={onRemove}
            aria-label="Remove attached image"
            title="Remove attachment"
          >
            ✕
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
