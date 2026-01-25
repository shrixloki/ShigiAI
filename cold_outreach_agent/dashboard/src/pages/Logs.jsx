import { useState, useEffect } from 'react'
import { getLogs } from '../api'

export default function Logs() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadLogs()
  }, [])

  async function loadLogs() {
    setLoading(true)
    const { data } = await getLogs({ limit: 50 })
    if (data) setLogs(data)
    setLoading(false)
  }

  return (
    <div className="animate-fade-in">
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3>System Event Logs</h3>
          <button className="btn btn-secondary" onClick={loadLogs}>Refresh</button>
        </div>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Module</th>
                <th>Action</th>
                <th>Actor</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="5" style={{ textAlign: 'center', padding: '24px' }}>Loading logs...</td></tr>
              ) : logs.length === 0 ? (
                <tr><td colSpan="5" style={{ textAlign: 'center', padding: '24px', color: 'var(--text-secondary)' }}>No logs found.</td></tr>
              ) : logs.map((log, i) => (
                <tr key={i}>
                  <td style={{ fontSize: '12px', whiteSpace: 'nowrap', color: 'var(--text-secondary)' }}>
                    {new Date(log.created_at || log.timestamp).toLocaleString()}
                  </td>
                  <td><span className="badge pending" style={{ color: 'var(--text-primary)', background: 'var(--bg-hover)' }}>{log.module || log.component || 'system'}</span></td>
                  <td style={{ fontWeight: '500' }}>{log.action || log.operation}</td>
                  <td>{log.actor || 'system'}</td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '13px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {JSON.stringify(log.details || log.metadata || log.context || {})}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
