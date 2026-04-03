import React, { useEffect, useMemo, useState } from 'react';

import {
  getRagAuditRuns,
  getRagAuditSessions,
  getRagAuditTimeline,
  getRagTrace,
} from '../api.js';

function formatDateTime(value) {
  if (!value) {
    return 'Not available';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return parsed.toLocaleString([], {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function roleCanFilterPatient(role) {
  const normalized = String(role || '').toLowerCase();
  return normalized === 'manager' || normalized === 'staff';
}

export default function TraceabilityPage({ currentUser }) {
  const role = String(currentUser?.role || '').toLowerCase();
  const canFilterPatient = roleCanFilterPatient(role);

  const [patientFilter, setPatientFilter] = useState('');
  const [modelFilter, setModelFilter] = useState('');
  const [offset, setOffset] = useState(0);
  const limit = 25;

  const [sessions, setSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError] = useState('');

  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [timeline, setTimeline] = useState({ session: null, turns: [], llm_runs: [] });
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineError, setTimelineError] = useState('');

  const [runs, setRuns] = useState([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsError, setRunsError] = useState('');

  const [tracePreviewById, setTracePreviewById] = useState({});
  const [traceLoadingId, setTraceLoadingId] = useState('');
  const [traceError, setTraceError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setSessionsLoading(true);
      setSessionsError('');
      try {
        const data = await getRagAuditSessions({
          patientId: canFilterPatient ? patientFilter : '',
          limit,
          offset,
        });
        if (!cancelled) {
          setSessions(Array.isArray(data) ? data : []);
          const hasSelection = (Array.isArray(data) ? data : []).some((item) => item.session_id === selectedSessionId);
          if (!hasSelection) {
            setSelectedSessionId((Array.isArray(data) && data[0]?.session_id) || '');
          }
        }
      } catch (error) {
        if (!cancelled) {
          setSessionsError(error.message || 'Unable to load sessions.');
          setSessions([]);
        }
      } finally {
        if (!cancelled) {
          setSessionsLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canFilterPatient, offset, patientFilter, selectedSessionId]);

  useEffect(() => {
    if (!selectedSessionId) {
      setTimeline({ session: null, turns: [], llm_runs: [] });
      return;
    }
    let cancelled = false;
    (async () => {
      setTimelineLoading(true);
      setTimelineError('');
      try {
        const data = await getRagAuditTimeline(selectedSessionId);
        if (!cancelled) {
          setTimeline({
            session: data?.session || null,
            turns: Array.isArray(data?.turns) ? data.turns : [],
            llm_runs: Array.isArray(data?.llm_runs) ? data.llm_runs : [],
          });
        }
      } catch (error) {
        if (!cancelled) {
          setTimelineError(error.message || 'Unable to load timeline.');
          setTimeline({ session: null, turns: [], llm_runs: [] });
        }
      } finally {
        if (!cancelled) {
          setTimelineLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedSessionId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setRunsLoading(true);
      setRunsError('');
      try {
        const data = await getRagAuditRuns({
          patientId: canFilterPatient ? patientFilter : '',
          sessionId: selectedSessionId || '',
          modelKey: modelFilter,
          limit: 100,
          offset: 0,
        });
        if (!cancelled) {
          setRuns(Array.isArray(data) ? data : []);
        }
      } catch (error) {
        if (!cancelled) {
          setRunsError(error.message || 'Unable to load run list.');
          setRuns([]);
        }
      } finally {
        if (!cancelled) {
          setRunsLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canFilterPatient, modelFilter, patientFilter, selectedSessionId]);

  const canPageBack = offset > 0;
  const canPageForward = sessions.length >= limit;

  const knownModelKeys = useMemo(() => {
    const keys = new Set();
    for (const item of runs) {
      if (item?.model_key) {
        keys.add(String(item.model_key));
      }
    }
    for (const item of timeline.llm_runs || []) {
      if (item?.model_key) {
        keys.add(String(item.model_key));
      }
    }
    return Array.from(keys).sort();
  }, [runs, timeline.llm_runs]);

  async function handleLoadTrace(traceId) {
    const key = String(traceId || '');
    if (!key || tracePreviewById[key]) {
      return;
    }
    setTraceError('');
    setTraceLoadingId(key);
    try {
      const detail = await getRagTrace(key);
      setTracePreviewById((current) => ({ ...current, [key]: detail }));
    } catch (error) {
      setTraceError(error.message || 'Unable to load trace details.');
    } finally {
      setTraceLoadingId('');
    }
  }

  return (
    <div className="page-container traceability-page">
      <header className="panel traceability-header-panel">
        <h2 className="section-title">Chat Session Traceability</h2>
        <p className="section-subtitle">
          Review patient sessions, turn-by-turn conversation events, retrieval trace IDs, and LLM run metadata for audit purposes.
        </p>
        <p className="muted small">Trace data may include sensitive patient messages. Access is scoped by role.</p>
      </header>

      <section className="panel traceability-filter-panel">
        <div className="traceability-filter-grid">
          {canFilterPatient ? (
            <div className="field">
              <label htmlFor="traceability-patient-filter">Patient ID</label>
              <input
                id="traceability-patient-filter"
                type="text"
                value={patientFilter}
                onChange={(event) => {
                  setOffset(0);
                  setPatientFilter(event.target.value);
                }}
                placeholder="Filter by patient id"
              />
            </div>
          ) : null}

          <div className="field">
            <label htmlFor="traceability-model-filter">Model key</label>
            <select
              id="traceability-model-filter"
              value={modelFilter}
              onChange={(event) => setModelFilter(event.target.value)}
            >
              <option value="">All models</option>
              {knownModelKeys.map((modelKey) => (
                <option key={modelKey} value={modelKey}>
                  {modelKey}
                </option>
              ))}
            </select>
          </div>

          <div className="traceability-filter-actions">
            <button
              className="btn secondary"
              onClick={() => {
                setPatientFilter('');
                setModelFilter('');
                setOffset(0);
              }}
              disabled={sessionsLoading || runsLoading}
            >
              Reset filters
            </button>
          </div>
        </div>
      </section>

      <div className="traceability-layout">
        <section className="panel traceability-sessions-panel">
          <div className="panel-heading-row">
            <div>
              <h3 className="section-title">Sessions</h3>
              <p className="section-subtitle">Select a session to inspect turns and runs.</p>
            </div>
            <div className="row">
              <button className="btn secondary" disabled={!canPageBack || sessionsLoading} onClick={() => setOffset((current) => Math.max(0, current - limit))}>
                Previous
              </button>
              <button className="btn secondary" disabled={!canPageForward || sessionsLoading} onClick={() => setOffset((current) => current + limit)}>
                Next
              </button>
            </div>
          </div>

          {sessionsLoading ? <p className="muted">Loading sessions...</p> : null}
          {sessionsError ? <div className="inline-notice error">{sessionsError}</div> : null}
          {!sessionsLoading && !sessionsError && sessions.length === 0 ? <p className="muted">No sessions found for this filter.</p> : null}

          <div className="traceability-session-list">
            {sessions.map((item) => {
              const isActive = selectedSessionId === item.session_id;
              return (
                <button
                  key={item.session_id}
                  className={`traceability-session-item ${isActive ? 'active' : ''}`}
                  onClick={() => setSelectedSessionId(item.session_id)}
                >
                  <div className="traceability-session-title">{item.session_id}</div>
                  <div className="muted small">patient: {item.patient_id}</div>
                  <div className="muted small">clinic: {item.clinic_id}</div>
                  <div className="muted small">turns: {item.turn_count} | runs: {item.run_count}</div>
                  <div className="muted small">started: {formatDateTime(item.started_at)}</div>
                </button>
              );
            })}
          </div>
        </section>

        <section className="panel traceability-detail-panel">
          <div className="panel-heading-row">
            <div>
              <h3 className="section-title">Session Timeline</h3>
              <p className="section-subtitle">
                {timeline.session?.session_id ? `session: ${timeline.session.session_id}` : 'Select a session to view detail.'}
              </p>
            </div>
          </div>

          {timelineLoading ? <p className="muted">Loading timeline...</p> : null}
          {timelineError ? <div className="inline-notice error">{timelineError}</div> : null}

          {!timelineLoading && !timelineError && timeline.session ? (
            <>
              <div className="traceability-session-meta muted small">
                patient: {timeline.session.patient_id} | clinic: {timeline.session.clinic_id} | started: {formatDateTime(timeline.session.started_at)}
              </div>

              <h4>Turns</h4>
              {timeline.turns.length === 0 ? <p className="muted">No turns recorded.</p> : null}
              <div className="traceability-turns-list">
                {timeline.turns.map((turn) => (
                  <div className="traceability-turn-card" key={turn.turn_id}>
                    <div className="traceability-turn-topline">
                      <strong>Turn {turn.turn_index}</strong>
                      <span className="muted small">
                        {turn.route} | {turn.status} | {turn.latency_ms ?? 0} ms
                      </span>
                    </div>
                    <div className="muted small">turn_id: {turn.turn_id}</div>
                    <div className="muted small">trace_id: {turn.trace_id || 'n/a'} | run_id: {turn.run_id || 'n/a'}</div>
                    <div className="traceability-turn-message"><strong>User:</strong> {turn.user_message || '-'}</div>
                    <div className="traceability-turn-message"><strong>Assistant:</strong> {turn.assistant_message || '-'}</div>
                    {turn.trace_id ? (
                      <div className="row">
                        <button
                          className="btn secondary"
                          disabled={traceLoadingId === turn.trace_id}
                          onClick={() => handleLoadTrace(turn.trace_id)}
                        >
                          {traceLoadingId === turn.trace_id ? 'Loading trace...' : 'Load trace'}
                        </button>
                      </div>
                    ) : null}
                    {turn.trace_id && tracePreviewById[turn.trace_id] ? (
                      <pre className="traceability-trace-preview">
                        {JSON.stringify(tracePreviewById[turn.trace_id], null, 2)}
                      </pre>
                    ) : null}
                  </div>
                ))}
              </div>

              <h4>LLM runs</h4>
              {runsLoading ? <p className="muted">Loading runs...</p> : null}
              {runsError ? <div className="inline-notice error">{runsError}</div> : null}
              {!runsLoading && !runsError && runs.length === 0 ? <p className="muted">No runs found for this selection.</p> : null}
              {!runsLoading && !runsError && runs.length > 0 ? (
                <div className="table-responsive">
                  <table className="results-table">
                    <thead>
                      <tr>
                        <th>Run ID</th>
                        <th>Model</th>
                        <th>Status</th>
                        <th>Turn ID</th>
                        <th>Trace ID</th>
                        <th>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runs.map((run) => (
                        <tr key={run.run_id}>
                          <td>{run.run_id}</td>
                          <td>{run.model_key}</td>
                          <td>{run.status}</td>
                          <td>{run.turn_id || '-'}</td>
                          <td>{run.trace_id || '-'}</td>
                          <td>{formatDateTime(run.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </>
          ) : null}

          {traceError ? <div className="inline-notice error">{traceError}</div> : null}
        </section>
      </div>
    </div>
  );
}
