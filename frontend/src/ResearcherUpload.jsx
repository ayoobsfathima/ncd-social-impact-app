import { useRef, useState } from "react";
import { scoreBatch, templateUrl } from "./api";

function downloadCsv(text, filename) {
  const blob = new Blob([text], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function ResearcherUpload() {
  const [fileName, setFileName] = useState(null);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);
  const [columnErrors, setColumnErrors] = useState(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);

  const handleFile = async (file) => {
    if (!file) return;
    setFileName(file.name);
    setError(null);
    setColumnErrors(null);
    setResponse(null);
    setLoading(true);
    try {
      const data = await scoreBatch(file);
      setResponse(data);
    } catch (err) {
      if (err.detail?.column_errors) {
        setColumnErrors(err.detail.column_errors);
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const rowFlags = response?.flags?.filter((f) => f.row_id !== "(column)") ?? [];
  const columnFlags = response?.flags?.filter((f) => f.row_id === "(column)") ?? [];

  return (
    <div className="two-col">
      <div className="panel form">
        <h2>Batch upload</h2>
        <p className="muted small">
          Upload a CSV that follows the required template exactly — same column
          names, same order, one row per respondent. Don't add, remove, or
          rename columns.
        </p>

        <a className="btn-ghost" href={templateUrl()} download>
          Download CSV template
        </a>

        <div
          className="dropzone"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            handleFile(e.dataTransfer.files?.[0]);
          }}
          onClick={() => inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv"
            style={{ display: "none" }}
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          <p><strong>{fileName || "Click to choose a CSV file"}</strong></p>
          <p className="muted small">or drag and drop it here</p>
        </div>

        {loading && <p className="muted">Scoring uploaded rows…</p>}
        {error && <p className="error">{error}</p>}
        {columnErrors && (
          <div className="notice notice-warn">
            <strong>This file doesn't match the template</strong>
            <ul>{columnErrors.map((e, i) => <li key={i}>{e}</li>)}</ul>
          </div>
        )}

        <div className="notice notice-info">
          <strong>How missing data is handled</strong>
          <ul>
            <li>A column with under 2% missing values is imputed with that column's median.</li>
            <li>A column with 2% or more missing is left as-is and flagged; those rows'
                domain averages are computed from the items that were answered.</li>
            <li>The reproduction item is imputed using age (0 for age 49+) then,
                if still missing, the median for that respondent's age group within the upload.</li>
            <li>The two caregiver-exhaustion items default to 0 when blank, matching
                the assumption that an unanswered item means no reported worry.</li>
          </ul>
        </div>
      </div>

      <div className="panel result-panel">
        <h2>Results</h2>
        {!response && <p className="muted">Upload a file to see a summary and download the scored CSV.</p>}
        {response && (
          <>
            <p>
              <strong>{response.n_rows}</strong> respondents scored.
              {" "}
              <button
                className="btn-primary"
                onClick={() => downloadCsv(response.csv, "ncd_scored_output.csv")}
              >
                Download scored CSV
              </button>
            </p>

            <h3 className="subhead">Column data-quality summary</h3>
            <table className="domain-table">
              <thead>
                <tr><th>Item</th><th>% missing</th><th>Handling</th></tr>
              </thead>
              <tbody>
                {Object.entries(response.column_summary).map(([item, s]) => (
                  <tr key={item}>
                    <td>{item}</td>
                    <td className="mono">{s.missing_pct}%</td>
                    <td className="small">{typeof s.imputed === "string" ? s.imputed : (s.imputed ? "median-imputed" : "left as-is")}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {columnFlags.length > 0 && (
              <div className="notice notice-warn">
                <strong>Columns needing attention</strong>
                <ul>{columnFlags.map((f, i) => <li key={i}>{f.field}: {f.detail}</li>)}</ul>
              </div>
            )}

            {rowFlags.length > 0 && (
              <div className="notice notice-warn">
                <strong>Row-level flags ({rowFlags.length})</strong>
                <div className="scroll-box">
                  <table className="domain-table small">
                    <thead><tr><th>Row id</th><th>Field</th><th>Issue</th><th>Value</th></tr></thead>
                    <tbody>
                      {rowFlags.map((f, i) => (
                        <tr key={i}>
                          <td>{f.row_id}</td>
                          <td>{f.field}</td>
                          <td>{f.issue.replaceAll("_", " ")}</td>
                          <td className="mono">{f.detail}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
