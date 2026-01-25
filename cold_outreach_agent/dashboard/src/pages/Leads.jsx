import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getLeads, bulkApproveLeads } from '../api'

export default function Leads() {
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(new Set())

  useEffect(() => {
    loadLeads()
  }, [page])

  async function loadLeads() {
    setLoading(true)
    const { data } = await getLeads({ page })
    if (data) {
      setLeads(data.leads || [])
      setTotal(data.pagination?.total || 0)
    }
    setLoading(false)
  }

  const toggleSelect = (id) => {
    const newSelected = new Set(selected)
    if (newSelected.has(id)) newSelected.delete(id)
    else newSelected.add(id)
    setSelected(newSelected)
  }

  const handleBulkApprove = async () => {
    if (selected.size === 0) return
    await bulkApproveLeads(Array.from(selected))
    setSelected(new Set())
    loadLeads()
  }

  return (
    <div className="animate-fade-in">
      {/* Controls */}
      <div className="card" style={{ marginBottom: '24px', padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '12px' }}>
          <input type="text" placeholder="Search leads..." className="input-field" style={{ width: '300px' }} />
          <select className="input-field" style={{ width: '150px' }}>
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
          </select>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          {selected.size > 0 && (
            <button className="btn btn-primary" onClick={handleBulkApprove}>
              Approve ({selected.size})
            </button>
          )}
          <button className="btn btn-secondary" onClick={() => loadLeads()}>Refresh</button>
        </div>
      </div>

      {/* Leads Table */}
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: '40px' }}><input type="checkbox" onChange={() => { }} /></th>
              <th>Business Name</th>
              <th>Status</th>
              <th>Quality</th>
              <th>Location</th>
              <th>Contact</th>
              <th>Discovered</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="8" style={{ textAlign: 'center', padding: '32px' }}>Loading leads...</td></tr>
            ) : leads.map(lead => (
              <tr key={lead.id} style={{ cursor: 'pointer' }}>
                <td onClick={(e) => e.stopPropagation()}>
                  <input type="checkbox" checked={selected.has(lead.id)} onChange={() => toggleSelect(lead.id)} />
                </td>
                <td>
                  <Link to={`/leads/${lead.id}`} style={{ color: 'var(--text-primary)', fontWeight: '600', textDecoration: 'none' }}>
                    {lead.business_name}
                  </Link>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{lead.website_url || 'No website'}</div>
                </td>
                <td>
                  <span className={`badge ${lead.review_status}`}>{lead.review_status}</span>
                </td>
                <td>
                  {/* Score Bar */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{ width: '60px', height: '4px', background: 'var(--bg-hover)', borderRadius: '2px' }}>
                      <div style={{
                        width: `${(lead.quality_score || 0) * 100}%`,
                        height: '100%',
                        background: (lead.quality_score > 0.7) ? 'var(--accent-primary)' : 'var(--accent-warning)',
                        borderRadius: '2px'
                      }}></div>
                    </div>
                  </div>
                </td>
                <td>{lead.location}</td>
                <td>
                  {lead.email ? (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
                      Email
                    </span>
                  ) : <span style={{ color: 'var(--text-tertiary)', fontSize: '12px' }}>--</span>}
                </td>
                <td style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  {new Date(lead.discovered_at).toLocaleDateString()}
                </td>
                <td>
                  <Link to={`/leads/${lead.id}`} className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '12px' }}>View</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {/* Pagination Footer - Simplified */}
        <div style={{ padding: '16px', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'center', gap: '16px' }}>
          <button className="btn btn-secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
          <span style={{ display: 'flex', alignItems: 'center', color: 'var(--text-secondary)' }}>Page {page} of {Math.ceil(total / 50)}</span>
          <button className="btn btn-secondary" disabled={page * 50 >= total} onClick={() => setPage(page + 1)}>Next</button>
        </div>
      </div>
    </div>
  )
}
