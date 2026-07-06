const P25 = 20.2;
const P75 = 39.9;

const bandColor = (severity) => {
  if (severity === "Low") return "var(--teal)";
  if (severity === "Moderate") return "var(--amber)";
  if (severity === "High") return "var(--brick)";
  return "var(--ink-faint)";
};

export default function ScoreDial({ score, severity }) {
  const clamped = Math.max(0, Math.min(100, score ?? 0));
  const trackTop = 20;
  const trackBottom = 220;
  const trackHeight = trackBottom - trackTop;
  const y = (pct) => trackBottom - (pct / 100) * trackHeight;
  const markerY = y(clamped);
  const color = bandColor(severity);

  return (
    <svg width="220" height="256" viewBox="0 0 220 256" role="img"
      aria-label={`Total social impact score ${score ?? "—"} out of 100, ${severity ?? "unscored"} severity`}>
      <text x="70" y={trackTop + 4} fontFamily="var(--font-mono)" fontSize="11" fill="var(--ink-muted)">100</text>
      <text x="70" y={trackBottom + 4} fontFamily="var(--font-mono)" fontSize="11" fill="var(--ink-muted)">0</text>

      <rect x="30" y={trackTop} width="16" height={trackHeight} rx="8" fill="var(--surface-sunken)" stroke="var(--border)" />
      <rect x="30" y={markerY} width="16" height={trackBottom - markerY} rx="8" fill={color} opacity="0.85" />

      <line x1="22" x2="54" y1={y(P25)} y2={y(P25)} stroke="var(--ink-faint)" strokeDasharray="2 2" />
      <text x="60" y={y(P25) + 4} fontFamily="var(--font-mono)" fontSize="11" fill="var(--ink-muted)">P25 · {P25}</text>

      <line x1="22" x2="54" y1={y(P75)} y2={y(P75)} stroke="var(--ink-faint)" strokeDasharray="2 2" />
      <text x="60" y={y(P75) + 4} fontFamily="var(--font-mono)" fontSize="11" fill="var(--ink-muted)">P75 · {P75}</text>

      <circle cx="38" cy="232" r="15" fill={color} />
      <circle cx="38" cy="232" r="15" fill="none" stroke="var(--border)" />

      <circle cx="38" cy={markerY} r="5" fill="var(--surface)" stroke={color} strokeWidth="3" />
      <text x="60" y={markerY + 4} fontFamily="var(--font-mono)" fontSize="12" fontWeight="600" fill={color}>
        {score != null ? score.toFixed(1) : "—"}
      </text>
    </svg>
  );
}
