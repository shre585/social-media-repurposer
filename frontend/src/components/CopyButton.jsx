import { useState } from "react";

export default function CopyButton({ text, label = "Copy", className = "" }) {
  const [done, setDone] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text || "");
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text || "";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    setDone(true);
    setTimeout(() => setDone(false), 1400);
  }
  return (
    <button type="button" className={`btn small ${className}`} onClick={copy}>
      {done ? "Copied ✓" : `📋 ${label}`}
    </button>
  );
}
