import React from "react";

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
        <div className="kpiRow">
          <div className="kpi">
            <div className="kpiLabel">Urgency band</div>
            <div className="kpiValue">{results.urgency_band}</div>
          </div>
          <div className="kpi">
            <div className="kpiLabel">Visit category</div>
            <div className="kpiValue">{results.visit_category}</div>
          </div>
        </div>

        <div className="kpiRow">
          <div className="kpi">
            <div className="kpiLabel">Wait estimate (P50)</div>
            <div className="kpiValue">{results.wait_p50_minutes} min</div>
          </div>
          <div className="kpi">
            <div className="kpiLabel">Wait estimate (P90)</div>
            <div className="kpiValue">{results.wait_p90_minutes} min</div>
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
