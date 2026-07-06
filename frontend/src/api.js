// Where the backend lives.
// - If VITE_API_BASE is set (e.g. for an ngrok tunnel), that wins.
// - In local development (npm run dev), default to the separate backend
//   process on port 8000.
// - In a production build served by the backend itself (single-service
//   hosting, e.g. Render), default to "" so requests go to the same
//   origin the page was loaded from (no separate address needed at all).
export const API_BASE =
  import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");

export async function getItemCatalogue() {
  const res = await fetch(`${API_BASE}/api/item-catalogue`);
  if (!res.ok) throw new Error("Could not reach the scoring server.");
  return res.json();
}

export async function scoreSingle(dob, answers) {
  const res = await fetch(`${API_BASE}/api/score-single`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dob, answers }),
  });
  if (!res.ok) throw new Error("Could not score this patient.");
  return res.json();
}

export async function scoreBatch(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/score-batch`, {
    method: "POST",
    body: form,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data?.detail;
    const msg = detail?.column_errors ? detail.column_errors.join(" ") : "Could not process this file.";
    const err = new Error(msg);
    err.detail = detail;
    throw err;
  }
  return data;
}

export function templateUrl() {
  return `${API_BASE}/api/template`;
}
