const iconPaths = {
  headphones: (
    <>
      <path d="M3 14v-3a9 9 0 0 1 18 0v3" />
      <rect x="3" y="13" width="4" height="7" rx="1.5" />
      <rect x="17" y="13" width="4" height="7" rx="1.5" />
    </>
  ),
  "shopping-cart": (
    <>
      <path d="M3 3h2l2.2 11a2 2 0 0 0 2 1.6h8.7a2 2 0 0 0 1.9-1.5L22 7H6" />
      <circle cx="10" cy="20" r="1.2" />
      <circle cx="18" cy="20" r="1.2" />
    </>
  ),
  smartphone: (
    <>
      <rect x="6" y="2.5" width="12" height="19" rx="2" />
      <path d="M10 18.5h4" />
    </>
  ),
  keyboard: (
    <>
      <rect x="2" y="5" width="20" height="14" rx="2" />
      <path d="M6 9h.01M9 9h.01M12 9h.01M15 9h.01M18 9h.01M6 12h.01M9 12h.01M12 12h.01M15 12h.01M18 12h.01M8 15h8" />
    </>
  ),
  "credit-card": (
    <>
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="M2 10h20M6 15h4" />
    </>
  ),
  zap: <path d="M13 2 4 14h7l-1 8 10-13h-7l1-7Z" />,
  scale: (
    <>
      <path d="M12 3v18M5 6h14M7 6l-4 7h8L7 6ZM17 6l-4 7h8l-4-7ZM8 21h8" />
    </>
  ),
  "map-pin": (
    <>
      <path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z" />
      <circle cx="12" cy="10" r="2.5" />
    </>
  ),
  package: (
    <>
      <path d="m12 3 9 5-9 5-9-5 9-5Z" />
      <path d="M3 8v9l9 5 9-5V8M12 13v9M7.5 5.5l9 5" />
    </>
  ),
  tag: (
    <>
      <path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V4h9l8.6 8.6a.6.6 0 0 1 0 .8Z" />
      <circle cx="7.5" cy="8.5" r="1" />
    </>
  ),
  settings: (
    <>
      <path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z" />
      <path d="m19.4 15 .1.1 1.3 1-1.5 2.6-1.6-.6a8 8 0 0 1-1.5.9l-.3 1.7h-3l-.3-1.7a8 8 0 0 1-1.5-.9l-1.6.6L6 16.1l1.3-1a8 8 0 0 1 0-1.8L6 12.2l1.5-2.6 1.6.6a8 8 0 0 1 1.5-.9l.3-1.7h3l.3 1.7a8 8 0 0 1 1.5.9l1.6-.6 1.5 2.6-1.3 1a8 8 0 0 1 .4 1.8Z" transform="translate(-1 -1) scale(1.08)" />
    </>
  ),
  search: (
    <>
      <circle cx="10.8" cy="10.8" r="6.8" />
      <path d="m16 16 5 5" />
    </>
  ),
  copy: (
    <>
      <rect x="8" y="8" width="12" height="12" rx="2" />
      <path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3" />
    </>
  ),
  check: <path d="m5 12 4 4L19 6" />,
  "check-circle": (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12 2.5 2.5L16 9" />
    </>
  ),
  trash: (
    <>
      <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 10v6M14 10v6" />
    </>
  ),
  moon: <path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5 8.6 8.6 0 1 0 20.5 14.2Z" />,
  eye: (
    <>
      <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6Z" />
      <circle cx="12" cy="12" r="2.5" />
    </>
  ),
  "eye-off": (
    <>
      <path d="m3 3 18 18M10.6 6.2A11 11 0 0 1 12 6c6.5 0 10 6 10 6a15 15 0 0 1-3.2 3.8M6.2 6.2C3.5 7.7 2 12 2 12s3.5 6 10 6c1.4 0 2.7-.3 3.8-.8" />
      <path d="M9.8 9.8a3 3 0 0 0 4.4 4.4" />
    </>
  ),
  x: <path d="m6 6 12 12M18 6 6 18" />,
  "arrow-up-right": <path d="M7 17 17 7M8 7h9v9" />,
};

export default function UiIcon({ name, size = 18, strokeWidth = 1.8, className }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {iconPaths[name] || iconPaths.package}
    </svg>
  );
}
