import React from "react";
import CircularCountdown from "./CircularCountdown";

export default function ResultsView({ results }) {
  if (!results) {
    return (
      <div>
        <h2>Results</h2>
        <div className="muted">Finish the intake to see operational outputs.</div>
      </div>
    );
  }

  return (
    <div>
      <h2>Results</h2>

      <div className="card">
        <div className="row">
          <div className="col-6 col-md-4 kpi">
            <div className="kpiLabel">Urgency band</div>
            <div className="kpiValue">{results.urgency_band}</div>
          </div>
          <div className="col-6 col-md-4 kpi">
            <div className="kpiLabel">Visit category</div>
            <div className="kpiValue">{results.visit_category}</div>
          </div>
          <div className="col-6 col-md-4 kpi" style={{ display: 'none' }}>
            <div className="kpiLabel">Wait estimate (P50)</div>
            <div className="kpiValue">
              <CircularCountdown minutes={results.wait_p50_minutes} label="P50" />
            </div>
          </div>
          <div className="col-6 col-md-4 kpi">
            <div className="kpiLabel">Wait estimate (P90)</div>
            <div className="kpiValue">
              <CircularCountdown minutes={results.wait_p90_minutes} label="P90" />
            </div>
          </div>
        </div>

        <div className="section">
          <div className="kpiLabel">Explanation</div>
          <div>{results.explanation}</div>
        </div>

        <div className="section muted">
          <div><strong>Important</strong></div>
          <div>This is not a diagnosis. Wait-time estimates are not guaranteed.</div>
        </div>

        <div className="section muted">
          {results.disclaimers?.map((d, idx) => (
            <div key={idx}>• {d}</div>
          ))}
        </div>

        <div className="section muted small">
          run_id: {results.run_id}
        </div>
      </div>
    </div>
  );
}
