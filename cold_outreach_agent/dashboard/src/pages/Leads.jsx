import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getLeads, approveLead, rejectLead, bulkApproveLeads, bulkRejectLeads } from '../api'

export default function Leads() {
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)
  const [stale, setStale] = useState(false)
  const [error, setError] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [filter, setFilter] = useState('all')
  
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  useEffect(() => {
    // Check URL params for initial filter
    const statusParam = searchParams.get('status')
    if (statusParam) {
      setFilter(statusParam)
    }
  }, [searchParams])

  useEffect(() => {
    loadLeads()
  }, [filter])

  async function loadLeads() {
    setLoading(true)
    const filters = {}
    if (filter !== 'all') {
      filters.review_status = filter
    }
    
    const res = await getLeads(filters)
    if (res.data) setLeads(res.data)
    setStale(res.stale)
    if (res.error && !res.data) setError(res.error)
    setLoading(false)
  }

  const handleApprove = async (leadId, e) => {
    e.stopPropagation()
    setActionError(null)
    const result = await approveLead(leadId)
    if (result.success) {
      loadLeads()
    } else {
      setActionError(result.error)
    }
  }

  const handleReject = async (leadId, e) => {
    e.stopPropagation()
    setActionError(null)
    const result = await rejectLead(leadId)
    if (result.success) {
      loadLeads()
    } else {
      setActionError(result.error)
    }
  }

  const handleBulkApprove = async () => {
    if (selectedIds.size === 0) return
    setActionError(null)
    const result = await bulkApproveLeads([...selectedIds])
    if (result.success) {
      setSelectedIds(new Set())
      loadLeads()
    } else {
      setActionError(result.error)
    }
  }

  const handleBulkReject = async () => {
    if (selectedIds.size === 0) return
    setActionError(null)
    const result = await bulkRejectLeads([...selectedIds])
    if (result.success) {
      setSelectedIds(new Set())
      loadLeads()
    } else {
      setActionError(result.error)
    }
  }

  const toggleSelect = (leadId, e) => {
    e.stopPropagation()
    const newSelected = new Set(selectedIds)
    if (newSelected.has(leadId)) {
      newSelected.delete(leadId)
    } else {
      newSelected.add(leadId)
    }
    setSelectedIds(newSelected)
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === leads.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(leads.map(l => l.lead_id)))
    }
  }

  if (loading) return <div className="loading">Loading...</div>
  if (error && !leads.length) return <div className="error">Failed to load: {error}</div>

  const pendingLeads = leads.filter(l => l.review_status === 'pending')
  const approvedLeads = leads.filter(l => l.review_status === 'approved')
  const rejectedLeads = leads.filter(l => l.review_status === 'rejected')

  return (
    <div>
      <h1 className="page-title">Lead Review</h1>
      
      {stale && <div className="warning">Backend unavailable. Showing last known data.</div>}
      {actionError && <div className="error">Action failed: {actionError}</div>}

      {/* Filter Tabs */}
      <div className="filter-tabs">
        <button 
          className={`tab ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All ({leads.length})
        </button>
        <button 
          className={`tab ${filter === 'pending' ? 'active' : ''}`}
          onClick={() => setFilter('pending')}
        >
          Pending ({pendingLeads.length})
        </button>
        <button 
          className={`tab ${filter === 'approved' ? 'active' : ''}`}
          onClick={() => setFilter('approved')}
        >
          Approved ({approvedLeads.length})
        </button>
        <button 
          className={`tab ${filter === 'rejected' ? 'active' : ''}`}
          onClick={() => setFilter('rejected')}
        >
          Rejected ({rejectedLeads.length})
        </button>
      </div>

      {/* Bulk Actions */}
      {selectedIds.size > 0 && (
        <div className="bulk-actions">
          <span>{selectedIds.size} selected</span>
          <button className="btn-approve" onClick={handleBulkApprove}>
            Approve Selected
          </button>
          <button className="btn-reject" onClick={handleBulkReject}>
            Reject Selected
          </button>
          <button className="btn-clear" onClick={() => setSelectedIds(new Set())}>
            Clear Selection
          </button>
        </div>
      )}

      {/* Leads Table */}
      <div className="card">
        <table>
          <thead>
            <tr>
              <th className="checkbox-col">
                <input 
                  type="checkbox" 
                  checked={selectedIds.size === leads.length && leads.length > 0}
                  onChange={toggleSelectAll}
                />
              </th>
              <th>Business</th>
              <th>Category</th>
              <th>Location</th>
              <th>Website</th>
              <th>Email</th>
              <th>Tag</th>
              <th>Review</th>
              <th>Outreach</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {leads.map(lead => (
              <tr 
                key={lead.lead_id} 
                className={`clickable ${selectedIds.has(lead.lead_id) ? 'selected' : ''}`}
                onClick={() => navigate(`/leads/${lead.lead_id}`)}
              >
                <td className="checkbox-col" onClick={(e) => e.stopPropagation()}>
                  <input 
                    type="checkbox" 
                    checked={selectedIds.has(lead.lead_id)}
                    onChange={(e) => toggleSelect(lead.lead_id, e)}
                  />
                </td>
                <td className="business-name">{lead.business_name}</td>
                <td>{lead.category || '-'}</td>
                <td className="location-cell">{lead.location || '-'}</td>
                <td>
                  {lead.website_url ? (
                    <a 
                      href={lead.website_url} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="website-link"
                    >
                      View
                    </a>
                  ) : '-'}
                </td>
                <td className="email-cell">{lead.email || <span className="no-email">No email</span>}</td>
                <td>{lead.tag ? <span className="tag">{lead.tag}</span> : '-'}</td>
                <td>
                  <span className={`review-status ${lead.review_status}`}>
                    {lead.review_status}
                  </span>
                </td>
                <td>
                  <span className={`outreach-status ${lead.outreach_status}`}>
                    {lead.outreach_status?.replace('_', ' ')}
                  </span>
                </td>
                <td className="actions-cell" onClick={(e) => e.stopPropagation()}>
                  {lead.review_status === 'pending' && (
                    <>
                      <button 
                        className="btn-approve-small"
                        onClick={(e) => handleApprove(lead.lead_id, e)}
                        title="Approve for outreach"
                      >
                        ✓
                      </button>
                      <button 
                        className="btn-reject-small"
                        onClick={(e) => handleReject(lead.lead_id, e)}
                        title="Reject"
                      >
                        ✗
                      </button>
                    </>
                  )}
                  {lead.review_status === 'approved' && (
                    <button 
                      className="btn-reject-small"
                      onClick={(e) => handleReject(lead.lead_id, e)}
                      title="Reject"
                    >
                      ✗
                    </button>
                  )}
                  {lead.review_status === 'rejected' && (
                    <button 
                      className="btn-approve-small"
                      onClick={(e) => handleApprove(lead.lead_id, e)}
                      title="Approve"
                    >
                      ✓
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {leads.length === 0 && (
              <tr>
                <td colSpan="10" className="empty-state">
                  {filter === 'pending' 
                    ? 'No leads pending review. Start discovery to find businesses.'
                    : filter === 'approved'
                    ? 'No approved leads. Review pending leads to approve them.'
                    : 'No leads yet. Start discovery to find businesses.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Help Text */}
      <div className="help-section">
        <h3>Review Process</h3>
        <ul>
          <li><strong>Pending:</strong> Newly discovered leads awaiting your review</li>
          <li><strong>Approved:</strong> Leads that will receive outreach emails</li>
          <li><strong>Rejected:</strong> Leads that will NOT receive any emails</li>
        </ul>
        <p className="safety-note">
          ⚠️ <strong>No emails are sent without your approval.</strong> Only approved leads will be contacted when you start outreach.
        </p>
      </div>
    </div>
  )
}
