import { useState, useEffect } from 'react'
import { getSystem } from '../api'

export default function System() {
  const [system, setSystem] = useState(null)

  useEffect(() => {
    getSystem().then(res => setSystem(res.data))
  }, [])

  if (!system) return <div className="loading">Loading configuration...</div>

  return (
    <div className="animate-fade-in">
      <div className="dashboard-grid">
        <div className="card">
          <h3>Environment</h3>
          <div className="table-container" style={{ marginTop: '16px', border: 'none' }}>
            <table className="data-table">
              <tbody>
                <tr>
                  <td>Environment</td>
                  <td style={{ textAlign: 'right', fontWeight: 'bold' }}>{system.environment || 'Production'}</td>
                </tr>
                <tr>
                  <td>Debug Mode</td>
                  <td style={{ textAlign: 'right' }}>
                    <span className={`badge ${system.debug_mode ? 'rejected' : 'approved'}`}>
                      {system.debug_mode ? 'Enabled' : 'Disabled'}
                    </span>
                  </td>
                </tr>
                <tr>
                  <td>Version</td>
                  <td style={{ textAlign: 'right' }}>1.0.0</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <h3>Configuration Security Check</h3>
          <div style={{ marginTop: '16px' }}>
            {system.configuration?.is_valid ? (
              <div style={{ padding: '12px', background: 'rgba(35, 134, 54, 0.15)', color: 'var(--accent-primary)', borderRadius: '6px' }}>
                All configurations are valid and secure.
              </div>
            ) : (
              <div style={{ padding: '12px', background: 'rgba(218, 54, 51, 0.15)', color: 'var(--accent-danger)', borderRadius: '6px' }}>
                Errors detected in configuration. Please review server logs.
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <h3>Sync & Integrations</h3>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>Manage external connections and API keys.</p>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Integration</th>
                <th>Status</th>
                <th>Last Sync</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Google Sheets</td>
                <td><span className="badge approved">Active</span></td>
                <td>Using 2-way sync</td>
                <td><button className="btn btn-secondary" style={{ fontSize: '11px', padding: '2px 8px' }}>Configure</button></td>
              </tr>
              <tr>
                <td>HubSpot CRM</td>
                <td><span className="badge pending">Inactive</span></td>
                <td>--</td>
                <td><button className="btn btn-secondary" style={{ fontSize: '11px', padding: '2px 8px' }}>Connect</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
