import csv
import io
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import scoring

app = FastAPI(title="NCD Social Impact Score API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local tool; tighten if you deploy this beyond your machine
    allow_methods=["*"],
    allow_headers=["*"],
)


class SinglePatientRequest(BaseModel):
    dob: str | None = None
    answers: dict


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/item-catalogue")
def item_catalogue():
    """Tells the frontend what items/labels/options to render, so the form
    always matches the scoring engine (single source of truth)."""
    return {
        "items": [
            {
                "key": k,
                "label": scoring.ITEM_LABELS[k],
                "type": (
                    "physical" if k in scoring.PHYSICAL_ITEMS
                    else "yesno" if k in scoring.YESNO_ITEMS
                    else "likert"
                ),
            }
            for k in scoring.ALL_SCORED_ITEMS
        ],
        "caregiver_item": scoring.CAREGIVER_FLAG_ITEM,
        "caregiver_domain_items": scoring.DOMAIN_ITEMS["caregiver"],
        "caregiver_domain_notice": (
            "This section (Domain 6) should be answered by the CAREGIVER, "
            "not the patient. If the patient does not have a caregiver, "
            "leave these questions blank."
        ),
        "domains": scoring.DOMAIN_LABELS,
        "cutoffs": {"p25": scoring.P25_CUTOFF, "p75": scoring.P75_CUTOFF},
    }


@app.post("/api/score-single")
def score_single(payload: SinglePatientRequest):
    result = scoring.score_single(payload.answers, dob_raw=payload.dob)
    return {
        "total_score": result.total_score,
        "severity": result.severity,
        "category_label": result.category_label,
        "interpretation": result.interpretation,
        "suggested_action": result.suggested_action,
        "domain_scores": result.domain_scores,
        "has_caregiver": result.has_caregiver,
        "age": result.age,
        "flags": [asdict(f) for f in result.flags],
        "notes": result.notes,
    }


@app.get("/api/interpretations")
def interpretations():
    """Static reference table (Low/Moderate/High -> interpretation +
    suggested action), so the frontend can render it as a standalone
    legend as well as inline with a specific patient's result."""
    return scoring.SEVERITY_INTERPRETATION


@app.get("/api/template")
def download_template():
    cols = scoring.REQUIRED_COLUMNS
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(cols)
    # one worked example row so users can see the expected value format
    example = {
        "id": "1001",
        "dob": "12/05/1968",  # DD/MM/YYYY = 12 May 1968
        "dom2_insurance": "no",
        "dom2_oope": "yes",
        "dom2_work_fear": "sometimes",
        "dom3_caregiver": "yes",
        "dom3_role": "rarely",
        "dom3_vacation": "frequently",
        "dom4_uncertainty": "sometimes",
        "dom4_reproduce": "",
        "dom4_stigma": "rarely",
        "dom4_exhausted": "sometimes",
        "dom4_overloaded": "rarely",
        "dom5_mobility": "some_problem",
        "dom5_pain": "no_pain",
        "dom6_help_more": "rarely",
        "dom6_no_time": "sometimes",
        "dom6_stressed": "sometimes",
        "dom6_privacy": "never",
        "dom6_depend": "rarely",
        "dom6_unable": "never",
    }
    writer.writerow([example.get(c, "") for c in cols])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ncd_score_template.csv"},
    )


@app.post("/api/score-batch")
async def score_batch(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    columns = reader.fieldnames or []
    col_errors = scoring.validate_columns(columns)
    if col_errors:
        raise HTTPException(status_code=400, detail={"column_errors": col_errors})

    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail={"column_errors": ["The uploaded file has no data rows."]})

    result_rows, flags, column_summary = scoring.score_batch(rows)

    # build downloadable CSV in-memory
    out_buf = io.StringIO()
    fieldnames = list(result_rows[0].keys())
    writer = csv.DictWriter(out_buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(result_rows)
    csv_text = out_buf.getvalue()

    return JSONResponse({
        "n_rows": len(result_rows),
        "results": result_rows,
        "flags": [asdict(f) for f in flags],
        "column_summary": column_summary,
        "csv": csv_text,
    })


# ---------------------------------------------------------------------------
# Serve the built frontend (frontend/dist), if present.
#
# This lets a single process serve both the API and the web page, so hosting
# providers only need one service instead of two. In local development,
# where you run `npm run dev` separately, frontend/dist won't exist and this
# block is simply skipped (no effect on the normal two-terminal workflow).
# Registered LAST, after every /api/... route above, so those always win.
# ---------------------------------------------------------------------------
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
