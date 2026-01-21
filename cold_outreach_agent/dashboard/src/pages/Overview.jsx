import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getOverview, getAgentState, startDiscovery, stopDiscovery, startOutreach, stopOutreach, pauseAgent, resumeAgent, resetAgent } from '../api'

export default function Overview() {
  const [overview, setOverview] = useState(null)
  const [agentState, setAgentState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [stale, setStale] = useState(false)
  const [error, setError] = useState(null)
  const [actionLoading, setActionLoading] = useState(null)
  const [actionError, setActionError] = useState(null)
  
  // Discovery form
  const [discoveryQuery, setDiscoveryQuery] = useState('')
  const [discoveryLocation, setDiscoveryLocation] = useState('')
  
  const navigate = useNavigate()

  useEffect(() => {
    async function load() {
      console.log('Loading data...')
      const [ovRes, stateRes] = await Promise.all([
        getOverview(),
        getAgentState()
      ])
      
      console.log('Overview response:', ovRes)
      console.log('Agent state response:', stateRes)
      
      if (ovRes.data) setOverview(ovRes.data)
      if (stateRes.data) setAgentState(stateRes.data)
      
      setStale(ovRes.stale || stateRes.stale)
      if (ovRes.error && !ovRes.data) setError(ovRes.error)
      
      setLoading(false)
    }
    load()
    const interval = setInterval(load, 3000)
    return () => clearInterval(interval)
  }, [])

  const handleAction = async (action, actionFn, ...args) => {
    setActionLoading(action)
    setActionError(null)
    
    const result = await actionFn(...args)
    
    if (!result.success) {
      setActionError(result.error)
    }
    
    setActionLoading(null)
  }

  const handleStartDiscovery = () => {
    if (!discoveryQuery.trim() || !discoveryLocation.trim()) {
      setActionError('Please enter both category and location')
      return
    }
    handleAction('discover', startDiscovery, discoveryQuery, discoveryLocation, 50)
  }

  if (loading) return <div className="loading">Loading...</div>
  if (error && !overview) return <div className="error">Failed to load: {error}</div>

  const state = agentState?.state || 'unknown'
  const isHealthy = agentState?.is_healthy ?? true
  
  // Button states
  const isIdle = state === 'idle'
  const isDiscovering = state === 'discovering'
  const isOutreachRunning = state === 'outreach_running'
  const isPaused = state === 'paused'
  const isError = state === 'error'
  const isStopping = state === 'stopping'

  console.log('Current state:', state, 'isIdle:', isIdle, 'agentState:', agentState)

  return (
    <div>
      <h1 className="page-title">Dashboard</h1>
      
      {stale && <div className="warning">Backend unavailable. Showing last known data.</div>}
      {actionError && <div className="error">Action failed: {actionError}</div>}

      {/* Agent Status */}
      <div className="card agent-status-card">
        <div className="card-header">Agent Status</div>
        <div className="card-body">
          <div className="agent-state-display">
            <span className={`state-indicator large ${state} ${!isHealthy ? 'unhealthy' : ''}`}></span>
            <span className="state-text">{state.toUpperCase().replace('_', ' ')}</span>
            {agentState?.current_task && <span className="current-task">({agentState.current_task})</span>}
          </div>
          {isDiscovering && agentState?.discovery_query && (
            <div className="discovery-info">
              Searching: <strong>{agentState.discovery_query}</strong> in <strong>{agentState.discovery_location}</strong>
            </div>
          )}
          {isError && agentState?.error_message && (
            <div className="error-notice">{agentState.error_message}</div>
          )}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card clickable" onClick={() => navigate('/leads?status=pending')}>
          <div className="label">Pending Review</div>
          <div className="value highlight">{overview?.pending_review || 0}</div>
        </div>
        <div className="stat-card clickable" onClick={() => navigate('/leads?status=approved')}>
          <div className="label">Approved</div>
          <div className="value">{overview?.approved || 0}</div>
        </div>
        <div className="stat-card">
          <div className="label">Emails Today</div>
          <div className="value">{overview?.emails_sent_today || 0}</div>
        </div>
        <div className="stat-card">
          <div className="label">Replies</div>
          <div className="value">{overview?.replies_received || 0}</div>
        </div>
      </div>

      {/* Discovery Control */}
      <div className="card">
        <div className="card-header">Discovery Control</div>
        <div className="card-body">
          <p className="help-text">Find businesses from Google Maps. Discovered leads require approval before outreach.</p>
          
          <div className="discovery-form">
            <div className="form-row">
              <input
                type="text"
                placeholder="Category (e.g., restaurants, plumbers)"
                value={discoveryQuery}
                onChange={(e) => setDiscoveryQuery(e.target.value)}
                disabled={!isIdle}
              />
              <input
                type="text"
                placeholder="Location (e.g., Austin, TX)"
                value={discoveryLocation}
                onChange={(e) => setDiscoveryLocation(e.target.value)}
                disabled={!isIdle}
              />
            </div>
            <div className="button-row">
              <button
                className="control-btn primary"
                onClick={handleStartDiscovery}
                disabled={!isIdle || actionLoading}
              >
                {actionLoading === 'discover' ? 'Starting...' : 'Start Discovery'}
              </button>
              {console.log('Discovery button disabled?', !isIdle || actionLoading, 'isIdle:', isIdle, 'actionLoading:', actionLoading)}
              
              {isDiscovering && (
                <button
                  className="control-btn"
                  onClick={() => handleAction('stop', stopDiscovery)}
                  disabled={actionLoading}
                >
                  {actionLoading === 'stop' ? 'Stopping...' : 'Stop Discovery'}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Outreach Control */}
      <div className="card">
        <div className="card-header">Outreach Control</div>
        <div className="card-body">
          <p className="help-text">
            Send emails to <strong>approved leads only</strong>. 
            {overview?.approved > 0 
              ? ` ${overview.approved} leads ready for outreach.`
              : ' No approved leads yet. Review and approve leads first.'}
          </p>
          
          <div className="button-row">
            <button
              className="control-btn primary"
              onClick={() => handleAction('outreach', startOutreach)}
              disabled={!isIdle || overview?.approved === 0 || actionLoading}
            >
              {actionLoading === 'outreach' ? 'Starting...' : 'Start Outreach'}
            </button>
            {console.log('Outreach button disabled?', !isIdle || overview?.approved === 0 || actionLoading, 'isIdle:', isIdle, 'approved:', overview?.approved, 'actionLoading:', actionLoading)}
            
            {isOutreachRunning && (
              <button
                className="control-btn"
                onClick={() => handleAction('stop', stopOutreach)}
                disabled={actionLoading}
              >
                {actionLoading === 'stop' ? 'Stopping...' : 'Stop Outreach'}
              </button>
            )}
            
            {(isDiscovering || isOutreachRunning) && (
              <button
                className="control-btn"
                onClick={() => handleAction('pause', pauseAgent)}
                disabled={actionLoading}
              >
                Pause
              </button>
            )}
            
            {isPaused && (
              <button
                className="control-btn"
                onClick={() => handleAction('resume', resumeAgent)}
                disabled={actionLoading}
              >
                Resume
              </button>
            )}
            
            {isError && (
              <button
                className="control-btn reset-btn"
                onClick={() => handleAction('reset', resetAgent)}
                disabled={actionLoading}
              >
                Reset from Error
              </button>
            )}
          </div>
          
          {isStopping && (
            <div className="stopping-notice">Agent is finishing current operation...</div>
          )}
        </div>
      </div>

      {/* Quick Stats */}
      <div className="card">
        <div className="card-header">Pipeline Summary</div>
        <div className="card-body">
          <div className="pipeline-stats">
            <div className="pipeline-item">
              <span className="label">Total Leads</span>
              <span className="value">{overview?.total_leads || 0}</span>
            </div>
            <div className="pipeline-arrow">→</div>
            <div className="pipeline-item">
              <span className="label">Pending</span>
              <span className="value">{overview?.pending_review || 0}</span>
            </div>
            <div className="pipeline-arrow">→</div>
            <div className="pipeline-item">
              <span className="label">Approved</span>
              <span className="value">{overview?.approved || 0}</span>
            </div>
            <div className="pipeline-arrow">→</div>
            <div className="pipeline-item">
              <span className="label">Sent</span>
              <span className="value">{(overview?.sent_initial || 0) + (overview?.sent_followup || 0)}</span>
            </div>
            <div className="pipeline-arrow">→</div>
            <div className="pipeline-item">
              <span className="label">Replied</span>
              <span className="value">{overview?.replies_received || 0}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
