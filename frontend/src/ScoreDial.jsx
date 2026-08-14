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
  const trackTop = 28;
  const trackBottom = 268;
  const trackHeight = trackBottom - trackTop;
  const y = (pct) => trackBottom - (pct / 100) * trackHeight;
  const markerY = y(clamped);
  const color = bandColor(severity);
  const tubeX = 44;
  const tubeWidth = 26;
  const bulbCx = tubeX + tubeWidth / 2;
  const bulbCy = 292;
  const bulbR = 24;

  return (
    <svg width="200" height="332" viewBox="0 0 200 332" role="img"
      aria-label={`Total social impact score ${score ?? "—"} out of 100, ${severity ?? "unscored"} severity`}>

      <text x={tubeX + tubeWidth / 2} y={trackTop - 10} textAnchor="middle"
        fontFamily="var(--font-mono)" fontSize="14" fontWeight="700" fill="var(--ink-muted)">100</text>
      <text x={tubeX + tubeWidth / 2} y={bulbCy - bulbR - 10} textAnchor="middle"
        fontFamily="var(--font-mono)" fontSize="14" fontWeight="700" fill="var(--ink-muted)">0</text>

      {/* tube background */}
      <rect x={tubeX} y={trackTop} width={tubeWidth} height={trackHeight} rx={tubeWidth / 2}
        fill="var(--surface-sunken)" stroke="var(--border)" strokeWidth="1.5" />

      {/* mercury fill */}
      <rect x={tubeX} y={markerY} width={tubeWidth} height={trackBottom - markerY} rx={tubeWidth / 2}
        fill={color} opacity="0.9" />

      {/* P25 / P75 reference lines */}
      <line x1={tubeX - 10} x2={tubeX + tubeWidth + 10} y1={y(P25)} y2={y(P25)}
        stroke="var(--ink-faint)" strokeWidth="1.5" strokeDasharray="3 3" />
      <text x={tubeX + tubeWidth + 16} y={y(P25) + 5} fontFamily="var(--font-mono)"
        fontSize="13" fontWeight="600" fill="var(--ink-muted)">P25 · {P25}</text>

      <line x1={tubeX - 10} x2={tubeX + tubeWidth + 10} y1={y(P75)} y2={y(P75)}
        stroke="var(--ink-faint)" strokeWidth="1.5" strokeDasharray="3 3" />
      <text x={tubeX + tubeWidth + 16} y={y(P75) + 5} fontFamily="var(--font-mono)"
        fontSize="13" fontWeight="600" fill="var(--ink-muted)">P75 · {P75}</text>

      {/* bulb */}
      <circle cx={bulbCx} cy={bulbCy} r={bulbR} fill={color} />
      <circle cx={bulbCx} cy={bulbCy} r={bulbR} fill="none" stroke="var(--border)" strokeWidth="1.5" />

      {/* marker on the tube at the current score */}
      <circle cx={bulbCx} cy={markerY} r="7" fill="var(--surface)" stroke={color} strokeWidth="4" />
    </svg>
  );
}
