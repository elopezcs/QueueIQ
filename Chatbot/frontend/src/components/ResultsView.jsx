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

  // Helper function to capitalize the first letter of a string
  const capitalizeFirstLetter = (string) => {
    if (!string) return string;
    return string.charAt(0).toUpperCase() + string.slice(1);
  };

  return (
    <div>
      <h2>Results</h2>

      <div className="card">
        <div className="kpiRow-4">
          <div className="kpi kpi-urgency">
            <div className="kpiLabel">Urgency band</div>
            <div className="kpiValue">{capitalizeFirstLetter(results.urgency_band)}</div>
          </div>
          <div className="kpi kpi-category">
            <div className="kpiLabel">Visit category</div>
            <div className="kpiValue">{capitalizeFirstLetter(results.visit_category)}</div>
          </div>
          <div className="kpi kpi-p50">
            <div className="kpiLabel">Typical Wait (P50)</div>
            <div className="kpiValue">
              <CircularCountdown minutes={results.wait_p50_minutes} label="P50" color="#03989e" />
            </div>
            <div className="kpiDescription">Half of patients wait less than this time.</div>
          </div>
          <div className="kpi kpi-p90">
            <div className="kpiLabel">Longer Wait (P90)</div>
            <div className="kpiValue">
              <CircularCountdown minutes={results.wait_p90_minutes} label="P90" color="#ff7b54" />
            </div>
            <div className="kpiDescription">9 out of 10 patients are seen before this time.</div>
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
