import React from "react";

/**
 * Custom Rich Markdown & Deal Link Renderer
 * Formats:
 * - **[Store]** [Title](url) -> Interactive Store Badge + Link Card
 * - [Title](url) -> Clickable Pill Link with External Arrow
 * - **Bold Text** -> <strong>
 * - *Italic Text* -> <em>
 * - • or - or * List items -> Formatted Bullet Item
 */
export default function MarkdownRenderer({ content }) {
  if (!content) return null;

  const lines = content.split("\n");

  const renderLine = (line, lineIndex) => {
    const trimmed = line.trim();
    if (!trimmed) return <div key={lineIndex} className="markdown-spacer" />;

    // Detect Bullet Points
    const isBullet = /^([•\-\*]|\d+\.)\s+/.test(trimmed);
    const cleanLine = isBullet ? trimmed.replace(/^([•\-\*]|\d+\.)\s+/, "") : line;

    // Pattern for Store + Link combo: **[Store Name]** [Product Title](URL) or [Store] [Title](URL)
    const storeLinkRegex = /(\*{0,2}\[([a-zA-Z0-9\s&'-]+)\]\*{0,2}\s*)?\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g;

    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = storeLinkRegex.exec(cleanLine)) !== null) {
      if (match.index > lastIndex) {
        parts.push(parseFormatting(cleanLine.substring(lastIndex, match.index), `${lineIndex}-${lastIndex}`));
      }

      const storeName = match[2];
      const linkTitle = match[3];
      const url = match[4];

      parts.push(
        <a
          key={`link-${lineIndex}-${match.index}`}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="rich-deal-link"
          title={`Open ${linkTitle}`}
        >
          {storeName && <span className="deal-store-badge">🏪 {storeName}</span>}
          <span className="deal-title">{linkTitle}</span>
          <span className="deal-arrow">↗</span>
        </a>
      );

      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < cleanLine.length) {
      parts.push(parseFormatting(cleanLine.substring(lastIndex), `${lineIndex}-${lastIndex}`));
    }

    if (isBullet) {
      return (
        <div key={lineIndex} className="markdown-bullet-row">
          <span className="bullet-dot">✦</span>
          <div className="bullet-content">{parts}</div>
        </div>
      );
    }

    return (
      <p key={lineIndex} className="markdown-paragraph">
        {parts}
      </p>
    );
  };

  return <div className="rich-markdown-container">{lines.map(renderLine)}</div>;
}

// Sub-parser for **bold**, *italic*, and `code`
function parseFormatting(text, keyPrefix) {
  if (!text) return null;

  // Split by bold (**text**), italic (*text*), and code (`text`)
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  const tokens = text.split(regex);

  return tokens.map((token, idx) => {
    const key = `${keyPrefix}-${idx}`;
    if (token.startsWith("**") && token.endsWith("**")) {
      return (
        <strong key={key} className="markdown-bold">
          {token.slice(2, -2)}
        </strong>
      );
    }
    if (token.startsWith("*") && token.endsWith("*")) {
      return (
        <em key={key} className="markdown-italic">
          {token.slice(1, -1)}
        </em>
      );
    }
    if (token.startsWith("`") && token.endsWith("`")) {
      return (
        <code key={key} className="markdown-code">
          {token.slice(1, -1)}
        </code>
      );
    }
    return token;
  });
}
