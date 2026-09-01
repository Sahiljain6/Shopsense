import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AI_ENGINES } from "../utils/constants";

export default function ModelDropdown({ selectedModel, onSelectModel }) {
  const [showModelMenu, setShowModelMenu] = useState(false);
  const modelMenuRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (modelMenuRef.current && !modelMenuRef.current.contains(event.target)) {
        setShowModelMenu(false);
      }
    }
    if (showModelMenu) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showModelMenu]);

  return (
    <div className="composer-model-wrapper" ref={modelMenuRef}>
      <button
        type="button"
        className="composer-model-pill interactive"
        onClick={() => setShowModelMenu((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={showModelMenu}
        title="Switch AI Shopping Engine"
      >
        <span className="model-dot"></span>
        <span className="model-name">{selectedModel}</span>
        <svg
          className={`model-chevron ${showModelMenu ? "open" : ""}`}
          width="7"
          height="5"
          viewBox="0 0 7 5"
          fill="none"
        >
          <path
            d="M1 1.5L3.5 3.5L6 1.5"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      <AnimatePresence>
        {showModelMenu && (
          <motion.div
            className="model-dropdown-menu"
            initial={{ opacity: 0, y: 8, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.96 }}
            transition={{ duration: 0.15 }}
            role="listbox"
          >
            <div className="dropdown-header">Select Engine</div>
            {AI_ENGINES.map((m) => (
              <button
                key={m.id}
                type="button"
                className={`model-option-item ${selectedModel === m.id ? "active" : ""}`}
                onClick={() => {
                  onSelectModel(m.id);
                  setShowModelMenu(false);
                }}
              >
                <div className="option-info">
                  <div className="option-title-row">
                    <span className="option-name">{m.id}</span>
                    <span className="option-badge">{m.badge}</span>
                  </div>
                  <span className="option-desc">{m.desc}</span>
                </div>
                {selectedModel === m.id && <span className="option-check">✓</span>}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
