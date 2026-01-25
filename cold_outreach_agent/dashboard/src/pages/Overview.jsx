import { useState, useEffect } from 'react'
import { getSystem, startDiscovery, stopDiscovery, startOutreach, stopOutreach, pauseAgent, resumeAgent } from '../api'

export default function Overview() {
  const [system, setSystem] = useState(null)

  useEffect(() => {
    loadSystem()
    const interval = setInterval(loadSystem, 5000)
    return () => clearInterval(interval)
  }, [])

  async function loadSystem() {
    const { data } = await getSystem()
    if (data) setSystem(data)
  }

  // Quick Actions Handlers
  const handleDiscoveryToggle = async () => {
    // Basic toggle logic - in real app would check state
    await startDiscovery('software agencies', 'New York')
    loadSystem()
  }

  if (!system) return <div className="loading">Initializing Mission Control...</div>

  const { lead_counts, email_statistics, configuration } = system

  return (
    <div className="animate-fade-in">
      {/* System Status Banner */}
      <div className="card" style={{ marginBottom: '24px', background: 'linear-gradient(135deg, rgba(35, 134, 54, 0.1), transparent)', borderColor: 'rgba(35, 134, 54, 0.3)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h2 style={{ fontSize: '18px', marginBottom: '4px', color: '#fff' }}>System Operational</h2>
            <p style={{ color: 'var(--accent-primary)', fontSize: '14px' }}>All agents active and monitoring</p>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button className="btn btn-secondary" onClick={handleDiscoveryToggle}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"></polygon></svg>
              Auto-Discovery
            </button>
            <button className="btn btn-primary">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
              Resume All
            </button>
          </div>
        </div>
      </div>

      <div className="dashboard-grid">
        {/* Pipeline Summary */}
        <div className="card">
          <h3>Pipeline Health</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Pending Review</span>
              <span className="badge pending">{lead_counts?.pending_review || 0}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Ready for Outreach</span>
              <span className="badge approved">{lead_counts?.approved || 0}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Active Campaigns</span>
              <span className="badge discovered">{lead_counts?.sent_initial || 0}</span>
            </div>
          </div>
        </div>

        {/* Email Performance */}
        <div className="card">
          <h3>Outreach Performance</h3>
          <div style={{ marginTop: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Deliverability</span>
              <span style={{ fontSize: '13px', fontWeight: '600' }}>98.2%</span>
            </div>
            <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', marginBottom: '16px' }}>
              <div style={{ width: '98.2%', height: '100%', background: 'var(--accent-primary)', borderRadius: '3px' }}></div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Daily Limit Usage</span>
              <span style={{ fontSize: '13px', fontWeight: '600' }}>45%</span>
            </div>
            <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px' }}>
              <div style={{ width: '45%', height: '100%', background: 'var(--accent-info)', borderRadius: '3px' }}></div>
            </div>
          </div>
        </div>

        {/* Recent Activity Log Preview */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <h3>Live System Events</h3>
          <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {[1, 2, 3].map(i => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '12px', background: 'var(--bg-panel)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-info)' }}></div>
                <span style={{ fontSize: '13px', fontWeight: '500', color: 'var(--text-secondary)', minWidth: '80px' }}>10:4{i} AM</span>
                <span style={{ fontSize: '14px' }}>Agent successfully enriched lead <strong>Acme Corp</strong> with contact data.</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
