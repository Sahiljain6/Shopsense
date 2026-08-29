import logoMarkUrl from "../assets/logo-mark.png";

export default function Logo({
  size = 34,
  showWordmark = true,
  subtitle = null,
  wordmarkClass = "",
  className = "",
  textColor = "inherit"
}) {
  return (
    <div
      className={`shopsense-brand-badge ${className}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "10px",
        color: textColor
      }}
    >
      <img
        src={logoMarkUrl}
        alt="ShopSense Mark"
        width={size}
        height={size}
        style={{
          height: `${size}px`,
          width: "auto",
          maxWidth: `${size * 1.25}px`,
          objectFit: "contain",
          filter: "drop-shadow(0 2px 10px rgba(6, 182, 212, 0.3))"
        }}
      />
      {showWordmark && (
        <div style={{ display: "flex", flexDirection: "column", lineHeight: 1 }}>
          <div
            className={`shopsense-wordmark ${wordmarkClass}`}
            style={{
              fontSize: `${Math.max(16, size * 0.58)}px`,
              letterSpacing: "-0.03em",
              userSelect: "none",
              display: "inline-flex",
              alignItems: "baseline"
            }}
          >
            <span style={{ fontWeight: 500, letterSpacing: "-0.02em" }}>shop</span>
            <span style={{ fontWeight: 800, letterSpacing: "-0.03em" }}>sense</span>
            <span
              style={{
                color: "#06b6d4",
                marginLeft: "2px",
                fontWeight: 900,
                fontSize: "1.2em",
                textShadow: "0 0 12px rgba(6, 182, 212, 0.7)"
              }}
            >
              •
            </span>
          </div>
          {subtitle && (
            <span
              style={{
                fontSize: "10px",
                fontWeight: 600,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                opacity: 0.6,
                marginTop: "3px"
              }}
            >
              {subtitle}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
