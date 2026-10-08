export default function TypingIndicator({ isWarmingUp = false, status = "Thinking..." }) {
  return (
    <div className="chat-typing-container" role="status" aria-label="AI is thinking">
      <div className="chat-typing-row">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
        {status && <span className="typing-status-text" style={{ marginLeft: "8px", fontSize: "0.8rem", color: "#94a3b8" }}>{status}</span>}
      </div>
      {isWarmingUp && (
        <div className="chat-warming-notice">
          <span>⚡</span> Waking up the server, this can take up to a minute...
        </div>
      )}
    </div>
  );
}
