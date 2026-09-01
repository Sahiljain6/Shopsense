export default function ChatHeaderBar({ title = "ShopSense", subtitle = "AI Assistant" }) {
  return (
    <div className="chatbot-widget-header">
      <div className="widget-header-left">
        <div className="widget-logo-box" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M4 7H20L18.5 17H5.5L4 7Z" stroke="#fff" strokeWidth="2.2" />
            <path
              d="M9 7V5C9 3.89543 9.89543 3 11 3H13C14.1046 3 15 3.89543 15 5V7"
              stroke="#fff"
              strokeWidth="2.2"
            />
          </svg>
        </div>
        <div className="widget-header-title">
          <span className="widget-title">{title}</span>
          <span className="widget-subtitle">{subtitle}</span>
        </div>
      </div>
      <div className="widget-controls" aria-hidden="true">
        <span className="control-btn">—</span>
        <span className="control-btn">□</span>
        <span className="control-btn">✕</span>
      </div>
    </div>
  );
}
