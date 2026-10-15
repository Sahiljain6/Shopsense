const humanize = (value) =>
  String(value ?? "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b[a-z]/g, (letter) => letter.toUpperCase());

export function formatProductAttributeLabel(label) {
  return humanize(label) || "Specification";
}

export function formatProductAttributeValue(value) {
  if (value === null || value === undefined || value === "") {
    return "Not specified";
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (Array.isArray(value)) {
    const formatted = value
      .map(formatProductAttributeValue)
      .filter((item) => item && item !== "Not specified");
    return formatted.length ? formatted.join(", ") : "Not specified";
  }

  if (typeof value === "object") {
    const entries = Object.entries(value).filter(
      ([, nestedValue]) => nestedValue !== null && nestedValue !== undefined && nestedValue !== "",
    );
    if (!entries.length) return "Not specified";

    return entries
      .map(([key, nestedValue]) => `${formatProductAttributeLabel(key)}: ${formatProductAttributeValue(nestedValue)}`)
      .join(" · ");
  }

  return String(value);
}
