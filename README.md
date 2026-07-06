# NCD Social Impact Score — web app

A small local web app that scores the NCD Social Impact Questionnaire, in two
modes:

- **Clinician mode** — fill in one patient's answers in a form, get their
  score and severity level immediately.
- **Researcher mode** — upload a CSV of many respondents (in a fixed
  template), get back the same CSV with two extra columns
  (`Total_Social_Impact`, `Severity`), plus a data-quality report.

It has two parts that both need to be running at the same time:

- `backend/` — a small Python server that does the scoring (FastAPI).
- `frontend/` — the web page you actually look at (React).

There is **no database**. Nothing you enter or upload is saved anywhere —
each score is calculated fresh and only lives in your browser tab until you
close it or refresh.

---

## 1. One-time setup

You need two pieces of free software installed on your computer. If you're
not sure whether you already have them, open a terminal (Terminal on
Mac, Command Prompt/PowerShell on Windows) and try the "check" command first.

### Python (3.10 or newer)
- Check: `python3 --version`
- If missing: download from https://www.python.org/downloads/ and install
  (on Windows, tick "Add Python to PATH" during install).

### Node.js (18 or newer) — this also installs `npm`
- Check: `node --version`
- If missing: download from https://nodejs.org (choose the "LTS" version)
  and install.

You only need to do this once per computer.

---

## 2. Install the app's dependencies

Open a terminal, navigate into the folder you unzipped this project into,
then run these commands **once**:

```bash
# Backend (Python) dependencies
cd backend
pip install -r requirements.txt --break-system-packages
cd ..

# Frontend (web page) dependencies
cd frontend
npm install
cd ..
```

This downloads the libraries the app needs. It can take a few minutes the
first time. You won't need to repeat this unless you move the project or
change the code.

---

## 3. Run the app

You need **two terminal windows/tabs open at the same time** — one for the
backend, one for the frontend. Leave both running while you use the app.

**Terminal 1 — start the backend:**
```bash
cd backend
python3 -m uvicorn main:app --reload --port 8000
```
Leave this running. You should see `Uvicorn running on http://127.0.0.1:8000`.

**Terminal 2 — start the frontend:**
```bash
cd frontend
npm run dev
```
Leave this running too. It will print a local address, normally
`http://localhost:5173`.

**Now open your browser** and go to:

```
http://localhost:5173
```

That's the app. When you're done, go back to both terminals and press
`Ctrl + C` to stop them.

Every time you want to use the app again later, you only need to repeat
this Step 3 (Step 2 is one-time, unless you move the folder).

---

## 4. Using the app

### Clinician tab
1. Enter the patient's date of birth (used only to correctly handle the
   "worried about having children" item for patients 49 and older).
2. Say whether the patient has a regular caregiver — this changes which
   weighting formula is used, exactly as in the validated scoring rules.
3. Answer whichever questionnaire items you have. You can leave any item
   blank; it will simply be left out of that domain's average rather than
   block the score.
4. Click **Calculate score**. You'll see:
   - the total score (0–100) and severity band (Low / Moderate / High),
     shown on a thermometer next to the P25/P75 cut-offs,
   - the five domain sub-scores,
   - any imputation notes (e.g. "reproduction item imputed to 0 because
     patient is 49+"),
   - any flags worth reviewing (e.g. an answer that didn't match a known
     category, or a missing caregiver status).

### Researcher tab
1. Click **Download CSV template** and use *that exact file* as your
   starting point — same column names, same order. Don't rename, add, or
   remove columns; the app checks this and will reject the file with an
   explanation if columns don't match.
2. Fill in one row per respondent, using the free-text labels shown in the
   template (`rarely`, `sometimes`, `no_problem`, `yes`, etc.) — the exact
   casing/spacing doesn't matter much, the app is fairly forgiving of
   variants (`Rarely`, `RARELY `, `rarely` all work), but the *word* has to
   be recognisable. If a cell doesn't match anything the app knows about,
   that respondent gets flagged rather than silently mis-scored.
3. Upload the file (click the box, or drag and drop).
4. You'll get:
   - a downloadable CSV with two new columns, `Total_Social_Impact` and
     `Severity`, plus per-domain sub-scores and computed age,
   - a **column data-quality summary** showing % missing per item and
     whether it was imputed,
   - a **row-level flag list** for anything that needs a second look
     (unrecognised values, unparseable dates, missing caregiver status,
     insufficient data to impute a value).

---

## 5. How the score is calculated (so you can audit it)

This logic is a direct translation of the validated R script you supplied
(`NCD_Questionnaire__P_and_C__and_P_scoring.R`), implemented in
`backend/scoring.py`. In short:

1. Each of the 18 scored items is recoded to a number (e.g. `rarely` → 1 on
   a 0–4 scale; `no_pain` → 0 on a 0–2 scale; `yes` → 0 / `no` → 1 for the
   two binary economic items).
2. Each item's numeric code is rescaled to 0–100 using that item's known
   maximum.
3. The five domain scores (Economic, Social, Psychological, Physical,
   Caregiver) are the **mean** of their items' 0–100 scores. If every item
   in a domain is missing, that domain scores 0.
4. The final score is a **weighted sum** of the domain scores. Two weight
   sets exist — one used when the respondent has a caregiver (5 domains
   contribute, including the Caregiver domain), one used when they don't
   (4 domains contribute; the Caregiver domain is dropped from the sum
   entirely, not just scored 0).
5. **Severity band** uses the fixed cut-offs you supplied from your
   reference sample: Low ≤ 20.2, Moderate 20.2–39.9, High > 39.9. These are
   hard-coded in `scoring.py` (`P25_CUTOFF`, `P75_CUTOFF`) — update them
   there if your reference sample changes.

### Where this app goes beyond the R script (by design, per your brief)
- **Flexible input matching.** The R script expected already-clean factor
  labels. This app accepts free-text labels *or* raw numeric codes, and
  normalises case/spacing/punctuation. Anything that still doesn't match a
  known category is treated as missing **and** separately flagged, rather
  than silently dropped or guessed.
- **Conditional imputation (<2% rule).** For general items (excluding the
  two bespoke rules below), a column is median-imputed only if fewer than
  2% of its values in the uploaded batch are missing. At 2% or more, values
  are left missing and the column is flagged, so the domain average is
  computed from whatever was answered rather than papering over a
  substantially incomplete item. This 2% rule is **not** in the original R
  script — it was added at your request and only applies in batch (CSV)
  mode, since single-patient mode has no dataset to compute a percentage
  from.
- **Two bespoke rules kept from the R script exactly:**
  - `dom4_reproduce` ("worried about being unable to have children"): if
    missing and age ≥ 49, set to 0; otherwise, in batch mode, imputed using
    the median for that respondent's age group (<25, 25–35, 36–44, 45–49,
    50+) within the same upload. In single-patient mode there is no batch to
    take a group median from, so it's simply left missing if the patient is
    under 49 and didn't answer (flagged as a note, not an error).
  - `dom4_exhausted` / `dom4_overloaded` (worry about caregiver
    exhaustion/overload): if missing, defaulted to 0, under the assumption
    (carried over from the R script) that an unanswered item here means no
    reported worry.
- **Missing caregiver status.** If `dom3_caregiver` itself is blank, the app
  can't know which weight set to apply. It defaults conservatively to "no
  caregiver" weighting and flags this clearly — this is an app-level
  judgement call, not something the R script had to handle (it assumed the
  field was always present), so please review any row flagged this way.

If any of these choices don't match how you want missingness handled,
they're all centralised in `backend/scoring.py` (see `score_batch` and
`score_single`) — no need to touch the frontend.

---

## 6. Project structure

```
ncd-app/
├── backend/
│   ├── main.py          FastAPI app: HTTP endpoints
│   ├── scoring.py        All scoring logic (single source of truth)
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.jsx              tab navigation shell
│       ├── ClinicianForm.jsx    single-patient form
│       ├── ResearcherUpload.jsx CSV batch upload
│       ├── ScoreDial.jsx        thermometer score visual
│       └── api.js               calls to the backend
└── README.md   (this file)
```

## 7. Permanent hosting (optional)

The backend can serve the built frontend itself, so the whole app can be
hosted as a **single service** (e.g. on Render's free tier), rather than
two separate ones:

- Build command: `pip install -r backend/requirements.txt && cd frontend && npm install && npm run build`
- Start command: `cd backend && python -m uvicorn main:app --host 0.0.0.0 --port $PORT`

Once `frontend/dist` exists (created by `npm run build`), `backend/main.py`
automatically serves the page, its assets, and the `/api/...` routes from
that one process — no separate frontend hosting, no CORS setup, and the
frontend's `api.js` automatically talks to the same origin it was loaded
from in this mode.

## 8. If something goes wrong

- **Frontend shows "Could not reach the scoring server"** — make sure
  Terminal 1 (the backend) is still running and shows no errors.
- **CSV rejected immediately** — the error message will list exactly which
  columns are missing or unexpected. Re-download the template and copy your
  data into it rather than editing your own file's headers.
- **A whole column is flagged as "high missingness"** — this means ≥2% of
  that column was blank, so the app didn't attempt to impute it. That's a
  data-completeness issue to take back to data collection, not a bug.
- **Port already in use** — if `8000` or `5173` are taken by something
  else on your machine, add `--port 8001` (backend) or the frontend will
  automatically offer the next free port.
