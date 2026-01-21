import { useState, useEffect } from 'react'
import { getLogs } from '../api'

export default function Logs() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [stale, setStale] = useState(false)
  const [error, setError] = useState(null)
  const [moduleFilter, setModuleFilter] = useState('')

  useEffect(() => {
    loadLogs()
  }, [moduleFilter])

  async function loadLogs() {
    setLoading(true)
    const filters = { limit: 200 }
    if (moduleFilter) filters.module = moduleFilter
    
    const res = await getLogs(filters)
    if (res.data) setLogs(res.data.logs || [])
    setStale(res.stale)
    if (res.error && !res.data) setError(res.error)
    setLoading(false)
  }

  if (loading) return <div className="loading">Loading...</div>
  if (error && !logs.length) return <div className="error">Failed to load: {error}</div>

  // Get unique modules for filter
  const modules = [...new Set(logs.map(l => l.module).filter(Boolean))]

  return (
    <div>
      <h1 className="page-title">Agent Logs</h1>
      
      {stale && <div className="warning">Backend unavailable. Showing last known data.</div>}

      {/* Filters */}
      <div className="filter-row">
        <select 
          value={moduleFilter} 
          onChange={(e) => setModuleFilter(e.target.value)}
          className="filter-select"
        >
          <option value="">All Modules</option>
          {modules.map(m => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        <button className="control-btn" onClick={loadLogs}>Refresh</button>
      </div>

      {/* Logs Table */}
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Module</th>
              <th>Lead ID</th>
              <th>Action</th>
              <th>Result</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log, i) => (
              <tr key={i}>
                <td className="timestamp-cell">
                  {new Date(log.timestamp).toLocaleString()}
                </td>
                <td>
                  <span className="module-badge">{log.module}</span>
                </td>
                <td>{log.lead_id || '-'}</td>
                <td>{log.action}</td>
                <td>
                  <span className={`result-badge ${log.result}`}>
                    {log.result}
                  </span>
                </td>
                <td className="details-cell">
                  {log.details || '-'}
                </td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr>
                <td colSpan="6" className="empty-state">
                  No logs recorded yet. Start discovery or outreach to see activity.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="help-section">
        <h3>Result Types</h3>
        <div className="legend">
          <span><span className="result-badge success">success</span> Action completed successfully</span>
          <span><span className="result-badge error">error</span> Action failed</span>
          <span><span className="result-badge warning">warning</span> Action completed with warnings</span>
          <span><span className="result-badge skipped">skipped</span> Action skipped (e.g., duplicate)</span>
          <span><span className="result-badge blocked">blocked</span> Action blocked (e.g., not approved)</span>
        </div>
      </div>
    </div>
  )
}
