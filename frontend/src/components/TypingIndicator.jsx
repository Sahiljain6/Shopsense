export default function TypingIndicator({ isWarmingUp = false }) {
  return (
    <div className="chat-typing-container" role="status" aria-label="AI is thinking">
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
  );
}
