import { useState } from "react";
import CopyButton from "./CopyButton.jsx";

export default function ExtrasPanel({ extras }) {
  const tabs = [
    extras.blog_markdown && { id: "blog", label: "📰 Blog post", text: extras.blog_markdown },
    extras.x_thread?.length && { id: "thread", label: "🧵 X thread", text: extras.x_thread.join("\n\n") },
    extras.linkedin_post && { id: "li", label: "💼 LinkedIn post", text: extras.linkedin_post },
    extras.seo_title && {
      id: "seo", label: "🔎 SEO",
      text: `Title: ${extras.seo_title}\n\nMeta description: ${extras.meta_description}\n\nKeywords: ${(extras.seo_keywords || []).join(", ")}`,
    },
    extras.chapters && { id: "chap", label: "⏱️ YouTube chapters", text: extras.chapters },
  ].filter(Boolean);
  const [tab, setTab] = useState(tabs[0]?.id);
  if (!tabs.length) return null;
  const active = tabs.find((t) => t.id === tab) || tabs[0];

  return (
    <section className="card extras">
      <h2 className="section-title">Bonus content</h2>
      <div className="tabs" role="tablist">
        {tabs.map((t) => (
          <button key={t.id} role="tab" aria-selected={active.id === t.id} className={active.id === t.id ? "on" : ""} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      <pre className="post-text tall">{active.text}</pre>
      <CopyButton text={active.text} label="Copy" className="primary" />
    </section>
  );
}
