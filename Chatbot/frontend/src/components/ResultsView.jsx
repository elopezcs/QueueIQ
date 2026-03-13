import React from "react";

export default function ResultsView({ results, clinic }) {
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

  // Helper function to get estimated time
  const getEstimatedTime = (minutes) => {
    const date = new Date(Date.now() + minutes * 60000);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  // Helper function to format minutes into hours and minutes
  const formatWaitTime = (totalMinutes) => {
    if (!totalMinutes) return "0 mins";
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    
    if (hours > 0) {
      const hrStr = `${hours} hr${hours > 1 ? 's' : ''}`;
      const minStr = minutes > 0 ? ` ${minutes} min${minutes > 1 ? 's' : ''}` : '';
      return hrStr + minStr;
    }
    return `${minutes} mins`;
  };

  return (
    <div>
      <h2>Results</h2>

      {clinic && (
        <div className="card" style={{ marginBottom: '24px', borderLeft: '4px solid var(--color-azure)' }}>
          <div style={{ fontSize: '0.9em', color: 'var(--color-azure)', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>Selected Clinic</div>
          <div style={{ fontSize: '1.2em', fontWeight: 'bold', marginBottom: '4px' }}>{clinic.name}</div>
          <div className="muted">{clinic.address_or_city}</div>
        </div>
      )}

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
            <div className="kpiLabel">Estimated Time to be Seen</div>
            <div className="kpiValue wait-time-value">
              <div className="wait-est">{getEstimatedTime(results.wait_p50_minutes)}</div>
              <div className="wait-mins">(Wait: {formatWaitTime(results.wait_p50_minutes)})</div>
            </div>
            <div className="kpiDescription">Typical wait time for similar cases.</div>
          </div>
          <div className="kpi kpi-p90">
            <div className="kpiLabel">Maximum Estimated Time</div>
            <div className="kpiValue wait-time-value">
              <div className="wait-est">{getEstimatedTime(results.wait_p90_minutes)}</div>
              <div className="wait-mins">(Wait: {formatWaitTime(results.wait_p90_minutes)})</div>
            </div>
            <div className="kpiDescription">90% of patients are seen before this time.</div>
          </div>
        </div>

        <div className="section explanation-box">
          <div className="kpiLabel">Explanation</div>
          <div className="explanation-content">
            {results.explanation?.split('\n').map((line, i) => (
              <p key={i}>{line}</p>
            ))}
          </div>
        </div>

        <div className="section disclaimer-box">
          <div className="disclaimer-title">Important</div>
          <div className="disclaimer-subtitle">This is not a diagnosis. Wait-time estimates are not guaranteed.</div>
          <div className="disclaimer-list">
            <div>• This tool provides operational guidance only. It is not a medical diagnosis.</div>
            <div>• If you think this is an emergency or severe, seek urgent in-person care or call local emergency services.</div>
            <div>• Wait-time estimates are not guaranteed and may change.</div>
          </div>
        </div>

        <div className="section muted small" style={{ marginTop: '16px' }}>
          run_id: {results.run_id}
        </div>
      </div>
    </div>
  );
}
