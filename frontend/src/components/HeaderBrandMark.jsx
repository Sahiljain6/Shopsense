export default function HeaderBrandMark({ size = 30 }) {
  return (
    <div className="fastshot-nav-brand">
      <svg className="fastshot-brand-mark" width={size} height={size} viewBox="0 0 34 34" aria-hidden="true">
        <circle cx="17" cy="17" r="17" fill="#9C86CE" />
        <circle cx="17" cy="17" r="8.6" fill="#FFFFFF" />
        <circle cx="17" cy="17" r="3.7" fill="#151519" />
      </svg>
      <div className="fastshot-brand-labels">
        <span className="fastshot-brand-title">ShopSense</span>
        <span className="fastshot-brand-sub">Fastshot AI Engine</span>
      </div>
    </div>
  );
}
