import { useState } from "react";
import ClinicianForm from "./ClinicianForm";
import ResearcherUpload from "./ResearcherUpload";
import "./App.css";

export default function App() {
  const [tab, setTab] = useState("clinician");

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="eyebrow">NCD Social Impact Questionnaire</div>
        <h1>Social Impact Score</h1>
        <p className="muted">
          Score a single patient, or upload a batch of respondents from a
          research dataset. Scoring logic is identical in both modes.
        </p>
      </header>

      <nav className="tabs" role="tablist">
        <button
          role="tab"
          aria-selected={tab === "clinician"}
          className={tab === "clinician" ? "tab active" : "tab"}
          onClick={() => setTab("clinician")}
        >
          Clinician · single patient
        </button>
        <button
          role="tab"
          aria-selected={tab === "researcher"}
          className={tab === "researcher" ? "tab active" : "tab"}
          onClick={() => setTab("researcher")}
        >
          Researcher · batch CSV
        </button>
      </nav>

      <main>
        {tab === "clinician" ? <ClinicianForm /> : <ResearcherUpload />}
      </main>

      <footer className="app-footer muted small">
        Cut-offs: Low ≤ 20.2 · Moderate 20.2–39.9 · High &gt; 39.9. No data leaves this
        server; nothing is stored between sessions.
      </footer>
    </div>
  );
}
