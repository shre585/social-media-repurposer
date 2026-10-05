export default function PlatformSelector({ platforms, selected, onToggle }) {
  return (
    <section aria-label="Choose platforms">
      <h2 className="section-title">Where are you posting?</h2>
      <div className="platform-grid">
        {platforms.map((p) => {
          const on = selected.includes(p.id);
          return (
            <button
              type="button" key={p.id} className={`platform ${on ? "on" : ""}`}
              aria-pressed={on} onClick={() => onToggle(p.id)}
            >
              <span className="p-emoji" aria-hidden="true">{p.emoji}</span>
              <span className="p-name">{p.label}</span>
              <span className="p-spec">{p.aspect} · up to {p.max_seconds >= 600 ? "10+ min" : `${p.max_seconds}s`}</span>
              <span className="p-check" aria-hidden="true">{on ? "✓" : ""}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
