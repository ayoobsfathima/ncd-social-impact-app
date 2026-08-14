import { useEffect, useState } from "react";
import { getItemCatalogue, scoreSingle } from "./api";
import ScoreDial from "./ScoreDial";

const LIKERT_OPTIONS = [
  ["not_at_all", "Not at all"],
  ["rarely", "Rarely"],
  ["sometimes", "Sometimes"],
  ["frequently", "Frequently"],
  ["almost_always", "Almost always"],
];
const MOBILITY_OPTIONS = [
  ["no_problem", "No problem moving around"],
  ["some_problem", "Some problem moving around"],
  ["bed", "Mostly confined to bed"],
];
const PAIN_OPTIONS = [
  ["no_pain", "No pain"],
  ["some_pain", "Some pain"],
  ["extreme", "Extreme pain"],
];
const YESNO_OPTIONS = [
  ["yes", "Yes"],
  ["no", "No"],
];

function optionsFor(item, type) {
  if (item === "dom5_mobility") return MOBILITY_OPTIONS;
  if (item === "dom5_pain") return PAIN_OPTIONS;
  if (type === "yesno") return YESNO_OPTIONS;
  return LIKERT_OPTIONS;
}

export default function ClinicianForm() {
  const [catalogue, setCatalogue] = useState(null);
  const [dob, setDob] = useState("");
  const [hasCaregiver, setHasCaregiver] = useState("");
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getItemCatalogue().then(setCatalogue).catch((e) => setError(e.message));
  }, []);

  const setAnswer = (item, value) => setAnswers((a) => ({ ...a, [item]: value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload = { ...answers, dom3_caregiver: hasCaregiver };
      const res = await scoreSingle(dob, payload);
      setResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setDob("");
    setHasCaregiver("");
    setAnswers({});
    setResult(null);
    setError(null);
  };

  if (!catalogue) {
    return <p className="muted">Loading questionnaire…</p>;
  }

  const showCaregiverItems = hasCaregiver === "yes";

  return (
    <div className="two-col">
      <form className="panel form" onSubmit={handleSubmit}>
        <h2>Patient entry</h2>
        <p className="muted small">
          Fill in what the patient reports. Any item can be left blank — it will
          simply be excluded from that domain's average rather than block scoring.
        </p>

        <div className="field-row">
          <label className="field">
            <span>Date of birth</span>
            <input
              type="text"
              placeholder="DD/MM/YYYY"
              value={dob}
              onChange={(e) => setDob(e.target.value)}
            />
            <span className="hint">DD/MM/YYYY. Used only to adjust the reproduction-related item for patients 49+.</span>
          </label>

          <label className="field">
            <span>Has a regular caregiver?</span>
            <select value={hasCaregiver} onChange={(e) => setHasCaregiver(e.target.value)}>
              <option value="">— Select —</option>
              {YESNO_OPTIONS.map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
            <span className="hint">Determines which domain-weight set is applied.</span>
          </label>
        </div>

        {["economic", "social", "psych", "phys", "caregiver"].map((domain) => {
          const items = catalogue.items.filter((it) => {
            const domainMap = {
              dom2_insurance: "economic", dom2_oope: "economic", dom2_work_fear: "economic",
              dom3_role: "social", dom3_vacation: "social",
              dom4_uncertainty: "psych", dom4_reproduce: "psych", dom4_stigma: "psych",
              dom4_exhausted: "psych", dom4_overloaded: "psych",
              dom5_mobility: "phys", dom5_pain: "phys",
              dom6_help_more: "caregiver", dom6_no_time: "caregiver", dom6_stressed: "caregiver",
              dom6_privacy: "caregiver", dom6_depend: "caregiver", dom6_unable: "caregiver",
            };
            return domainMap[it.key] === domain;
          });
          if (domain === "caregiver" && !showCaregiverItems) return null;
          return (
            <fieldset key={domain} className={`domain-group${domain === "caregiver" ? " domain-group-caregiver" : ""}`}>
              <legend>{catalogue.domains[domain]}</legend>
              {domain === "caregiver" && catalogue.caregiver_domain_notice && (
                <div className="notice notice-warn caregiver-notice">
                  <strong>⚠ To be answered by the caregiver</strong>
                  <p style={{ margin: "4px 0 0" }}>{catalogue.caregiver_domain_notice}</p>
                </div>
              )}
              {items.map((it) => (
                <label className="field" key={it.key}>
                  <span>{it.label}</span>
                  <select value={answers[it.key] ?? ""} onChange={(e) => setAnswer(it.key, e.target.value)}>
                    <option value="">— Not answered —</option>
                    {optionsFor(it.key, it.type).map(([v, l]) => (
                      <option key={v} value={v}>{l}</option>
                    ))}
                  </select>
                </label>
              ))}
            </fieldset>
          );
        })}

        <div className="button-row">
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Scoring…" : "Calculate score"}
          </button>
          <button type="button" className="btn-ghost" onClick={handleReset}>
            Clear form
          </button>
        </div>

        {error && <p className="error">{error}</p>}
      </form>

      <div className="panel result-panel">
        <h2>Result</h2>
        {!result && <p className="muted">Complete the form and calculate to see the score here.</p>}
        {result && (
          <>
            <div className="dial-row">
              <ScoreDial score={result.total_score} severity={result.severity} />
              <div>
                <div className={`severity-badge severity-${(result.severity || "").toLowerCase()}`}>
                  {result.severity}
                </div>
                <div className="score-number">{result.total_score?.toFixed(1)}<span className="muted"> / 100</span></div>
                <p className="muted small">
                  Age at scoring: {result.age ?? "unknown"} · Caregiver weighting: {result.has_caregiver ? "with caregiver" : "without caregiver"}
                </p>
              </div>
            </div>

            {result.interpretation && (
              <div className="notice notice-info interpretation-box">
                <strong>{result.category_label}</strong>
                <p style={{ margin: "6px 0 10px" }}>{result.interpretation}</p>
                <strong>Suggested action</strong>
                <p style={{ margin: "6px 0 0" }}>{result.suggested_action}</p>
              </div>
            )}

            <h3 className="subhead">Domain breakdown</h3>
            <p className="muted small" style={{ margin: "-4px 0 12px" }}>
              Each domain is scored independently on a 0–100 scale. They're combined
              with different weights to produce the total score above, so they won't
              add up to it — this just shows which areas are contributing most.
            </p>
            <div className="domain-bars">
              {Object.entries(result.domain_scores)
                .sort((a, b) => b[1] - a[1])
                .map(([d, v]) => (
                  <div className="domain-bar-row" key={d}>
                    <span className="domain-bar-label">{catalogue.domains[d]}</span>
                    <div className="domain-bar-track">
                      <div className="domain-bar-fill" style={{ width: `${Math.max(0, Math.min(100, v))}%` }} />
                    </div>
                    <span className="domain-bar-value mono">{v.toFixed(1)}</span>
                  </div>
                ))}
            </div>

            {result.notes.length > 0 && (
              <div className="notice notice-info">
                <strong>Imputation notes</strong>
                <ul>{result.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
              </div>
            )}
            {result.flags.length > 0 && (
              <div className="notice notice-warn">
                <strong>Please review</strong>
                <ul>
                  {result.flags.map((f, i) => (
                    <li key={i}>{f.field}: {f.issue.replaceAll("_", " ")} {f.detail ? `— ${f.detail}` : ""}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
