import { useState, useEffect, useCallback } from 'react'
import { 
  getSystem, 
  getAgentState, 
  startDiscovery,
  stopDiscovery,
  startOutreach,
  stopOutreach,
  pauseAgent, 
  resumeAgent, 
  stopAgent,
  resetAgent,
  getControlLogs
} from '../api'

export default function System() {
  const [system, setSystem] = useState(null)
  const [agentState, setAgentState] = useState(null)
  const [controlLogs, setControlLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [stale, setStale] = useState(false)
  const [error, setError] = useState(null)
  const [actionLoading, setActionLoading] = useState(null)
  const [actionError, setActionError] = useState(null)

  const loadData = useCallback(async () => {
    const [sysRes, stateRes, logsRes] = await Promise.all([
      getSystem(),
      getAgentState(),
      getControlLogs(20)
    ])
    
    if (sysRes.data) setSystem(sysRes.data)
    if (stateRes.data) setAgentState(stateRes.data)
    if (logsRes.data) setControlLogs(logsRes.data.logs || [])
    
    setStale(sysRes.stale || stateRes.stale)
    if ((sysRes.error && !sysRes.data) || (stateRes.error && !stateRes.data)) {
      setError(sysRes.error || stateRes.error)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 3000)
    return () => clearInterval(interval)
  }, [loadData])

  const handleAction = async (action, actionFn, ...args) => {
    setActionLoading(action)
    setActionError(null)
    
    const result = await actionFn(...args)
    
    if (!result.success) {
      setActionError(result.error)
    }
    
    await loadData()
    setActionLoading(null)
  }

  if (loading) return <div className="loading">Loading...</div>
  if (error && !system) return <div className="error">Failed to load: {error}</div>

  const state = agentState?.state || 'unknown'
  const isHealthy = agentState?.is_healthy ?? true
  const quotaPercent = system ? Math.round((system.emails_sent_today / system.email_quota) * 100) : 0

  // State checks
  const isIdle = state === 'idle'
  const isDiscovering = state === 'discovering'
  const isOutreachRunning = state === 'outreach_running'
  const isPaused = state === 'paused'
  const isError = state === 'error'
  const isStopping = state === 'stopping'
  const isRunning = isDiscovering || isOutreachRunning

  return (
    <div>
      <h1 className="page-title">System Health</h1>
      
      {stale && <div className="warning">Backend unavailable. Showing last known data.</div>}
      {actionError && <div className="error">Action failed: {actionError}</div>}

      {/* Agent Control Panel */}
      <div className="card agent-control">
        <div className="card-header">Agent Control</div>
        <div className="card-body">
          <div className="agent-status-row">
            <div className="agent-state">
              <span className={`state-indicator large ${state} ${!isHealthy ? 'unhealthy' : ''}`}></span>
              <span className="state-label">{state.toUpperCase().replace('_', ' ')}</span>
              {!isHealthy && <span className="health-warning">({agentState?.health_reason})</span>}
            </div>
          </div>

          {/* Current Task Info */}
          {agentState?.current_task && (
            <div className="current-task-info">
              <strong>Current Task:</strong> {agentState.current_task}
            </div>
          )}
          
          {isDiscovering && agentState?.discovery_query && (
            <div className="discovery-info">
              <strong>Discovery:</strong> {agentState.discovery_query} in {agentState.discovery_location}
            </div>
          )}

          {isStopping && (
            <div className="stopping-notice">
              Agent is finishing current operation and will stop shortly...
            </div>
          )}

          {isError && agentState?.error_message && (
            <div className="error-notice">
              <strong>Error:</strong> {agentState.error_message}
            </div>
          )}

          {/* Control Buttons */}
          <div className="agent-controls">
            {isRunning && (
              <>
                <button 
                  className="control-btn"
                  onClick={() => handleAction('pause', pauseAgent)}
                  disabled={actionLoading}
                >
                  {actionLoading === 'pause' ? 'Pausing...' : 'Pause'}
                </button>
                <button 
                  className="control-btn"
                  onClick={() => handleAction('stop', stopAgent)}
                  disabled={actionLoading}
                >
                  {actionLoading === 'stop' ? 'Stopping...' : 'Stop'}
                </button>
              </>
            )}
            
            {isPaused && (
              <>
                <button 
                  className="control-btn"
                  onClick={() => handleAction('resume', resumeAgent)}
                  disabled={actionLoading}
                >
                  {actionLoading === 'resume' ? 'Resuming...' : 'Resume'}
                </button>
                <button 
                  className="control-btn"
                  onClick={() => handleAction('stop', stopAgent)}
                  disabled={actionLoading}
                >
                  {actionLoading === 'stop' ? 'Stopping...' : 'Stop'}
                </button>
              </>
            )}

            {isError && (
              <button 
                className="control-btn reset-btn"
                onClick={() => handleAction('reset', resetAgent)}
                disabled={actionLoading}
              >
                {actionLoading === 'reset' ? 'Resetting...' : 'Reset from Error'}
              </button>
            )}
          </div>

          {/* Agent Metadata */}
          <div className="agent-meta">
            <div className="meta-item">
              <span className="meta-label">Last Transition:</span>
              <span className="meta-value">
                {agentState?.last_transition_time 
                  ? new Date(agentState.last_transition_time).toLocaleString()
                  : 'Never'}
              </span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Last Heartbeat:</span>
              <span className="meta-value">
                {agentState?.last_heartbeat 
                  ? new Date(agentState.last_heartbeat).toLocaleString()
                  : 'None'}
              </span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Controlled By:</span>
              <span className="meta-value">{agentState?.controlled_by || 'system'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="label">Health Status</div>
          <div className="value system-status">
            <span className={`status-dot ${!isHealthy || system?.error_count_24h > 5 ? 'error' : ''}`}></span>
            {isHealthy ? 'Healthy' : 'Unhealthy'}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Errors (24h)</div>
          <div className="value">{system?.error_count_24h || 0}</div>
        </div>
        <div className="stat-card">
          <div className="label">Email Quota</div>
          <div className="value">{system?.emails_sent_today || 0} / {system?.email_quota || 0}</div>
        </div>
      </div>

      {/* Lead Counts */}
      {system?.lead_counts && (
        <div className="card">
          <div className="card-header">Lead Statistics</div>
          <div className="card-body">
            <div className="detail-grid">
              <div className="detail-item">
                <div className="label">Total Leads</div>
                <div className="value">{system.lead_counts.total}</div>
              </div>
              <div className="detail-item">
                <div className="label">Pending Review</div>
                <div className="value">{system.lead_counts.pending_review}</div>
              </div>
              <div className="detail-item">
                <div className="label">Approved</div>
                <div className="value">{system.lead_counts.approved}</div>
              </div>
              <div className="detail-item">
                <div className="label">Rejected</div>
                <div className="value">{system.lead_counts.rejected}</div>
              </div>
              <div className="detail-item">
                <div className="label">Sent Initial</div>
                <div className="value">{system.lead_counts.sent_initial}</div>
              </div>
              <div className="detail-item">
                <div className="label">Sent Follow-up</div>
                <div className="value">{system.lead_counts.sent_followup}</div>
              </div>
              <div className="detail-item">
                <div className="label">Replied</div>
                <div className="value">{system.lead_counts.replied}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Configuration */}
      <div className="card">
        <div className="card-header">Configuration</div>
        <div className="card-body">
          <div className="detail-grid">
            <div className="detail-item">
              <div className="label">Max Emails Per Day</div>
              <div className="value">{system?.email_quota || '-'}</div>
            </div>
            <div className="detail-item">
              <div className="label">Follow-up Delay</div>
              <div className="value">3 days</div>
            </div>
          </div>
        </div>
      </div>

      {/* Control Audit Log */}
      <div className="card">
        <div className="card-header">Control Log</div>
        <div className="card-body">
          {controlLogs.length === 0 ? (
            <div className="empty-state">No control actions recorded yet.</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Transition</th>
                  <th>By</th>
                  <th>Reason</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {controlLogs.map((log, i) => (
                  <tr key={i}>
                    <td>{new Date(log.timestamp).toLocaleString()}</td>
                    <td>{log.previous_state} → {log.new_state}</td>
                    <td>{log.controlled_by}</td>
                    <td>{log.reason || '-'}</td>
                    <td>
                      <span className={`result-badge ${log.result}`}>
                        {log.result}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
