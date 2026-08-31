import React from "react";

/**
 * Custom Rich Markdown, Table & Deal Link Renderer
 * Formats:
 * - Headings: ### Title, #### Title
 * - Tables: | Header | Header | -> Responsive styled <table>
 * - **[Store]** [Title](url) -> Interactive Store Badge + Link Card
 * - [Title](url) -> Clickable Pill Link with External Arrow
 * - **Bold Text** -> <strong>
 * - *Italic Text* -> <em>
 * - • or - or * List items -> Formatted Bullet Item
 */
export default function MarkdownRenderer({ content }) {
  if (!content) return null;

  const rawLines = content.split("\n");
  const blocks = [];
  let currentTable = null;

  for (let i = 0; i < rawLines.length; i++) {
    const line = rawLines[i];
    const trimmed = line.trim();

    // Check if line is a table row (starts and ends with | or contains multiple |)
    const isTableRow = trimmed.startsWith("|") && trimmed.endsWith("|") && trimmed.includes("|");

    if (isTableRow) {
      if (!currentTable) {
        currentTable = [];
      }
      currentTable.push(trimmed);
      continue;
    } else {
      if (currentTable) {
        blocks.push({ type: "table", rows: currentTable, index: i - currentTable.length });
        currentTable = null;
      }
      blocks.push({ type: "line", content: line, index: i });
    }
  }

  if (currentTable) {
    blocks.push({ type: "table", rows: currentTable, index: rawLines.length - currentTable.length });
  }

  return (
    <div className="rich-markdown-container">
      {blocks.map((block) => {
        if (block.type === "table") {
          return renderTable(block.rows, block.index);
        }
        return renderLine(block.content, block.index);
      })}
    </div>
  );
}

function renderTable(rows, tableIndex) {
  if (rows.length < 2) return null;

  // Filter out separator row like |:---|:---|
  const dataRows = [];
  let headerRow = null;

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const cells = row
      .split("|")
      .slice(1, -1)
      .map((c) => c.trim());

    // Check if this is separator row
    const isSeparator = cells.every((c) => /^:?-+:?$/.test(c));
    if (isSeparator) {
      continue;
    }

    if (!headerRow) {
      headerRow = cells;
    } else {
      dataRows.push(cells);
    }
  }

  if (!headerRow) return null;

  return (
    <div key={`tbl-wrap-${tableIndex}`} className="markdown-table-wrapper">
      <table className="markdown-table">
        <thead>
          <tr>
            {headerRow.map((cell, idx) => (
              <th key={`th-${tableIndex}-${idx}`}>{parseFormatting(cell, `th-${idx}`)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {dataRows.map((row, rIdx) => (
            <tr key={`tr-${tableIndex}-${rIdx}`}>
              {row.map((cell, cIdx) => (
                <td key={`td-${tableIndex}-${rIdx}-${cIdx}`}>
                  {parseFormatting(cell, `td-${rIdx}-${cIdx}`)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderLine(line, lineIndex) {
  const trimmed = line.trim();
  if (!trimmed) return <div key={`spacer-${lineIndex}`} className="markdown-spacer" />;

  // Headings
  if (trimmed.startsWith("#### ")) {
    const text = trimmed.replace(/^####\s+/, "");
    return (
      <h4 key={`h4-${lineIndex}`} className="markdown-h4">
        {parseFormatting(text, `h4-${lineIndex}`)}
      </h4>
    );
  }

  if (trimmed.startsWith("### ")) {
    const text = trimmed.replace(/^###\s+/, "");
    return (
      <h3 key={`h3-${lineIndex}`} className="markdown-h3">
        {parseFormatting(text, `h3-${lineIndex}`)}
      </h3>
    );
  }

  // Bullet Points
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
      <div key={`bullet-${lineIndex}`} className="markdown-bullet-row">
        <span className="bullet-dot">✦</span>
        <div className="bullet-content">{parts}</div>
      </div>
    );
  }

  return (
    <p key={`p-${lineIndex}`} className="markdown-paragraph">
      {parts}
    </p>
  );
}

// Sub-parser for **bold**, *italic*, and `code`
function parseFormatting(text, keyPrefix) {
  if (!text) return null;

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
