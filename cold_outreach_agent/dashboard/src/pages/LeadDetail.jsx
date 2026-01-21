import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { getLeadDetail, approveLead, rejectLead } from '../api'

export default function LeadDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionError, setActionError] = useState(null)

  useEffect(() => {
    loadLead()
  }, [id])

  async function loadLead() {
    const res = await getLeadDetail(id)
    if (res.data) setData(res.data)
    if (res.error) setError(res.error)
    setLoading(false)
  }

  const handleApprove = async () => {
    setActionError(null)
    const result = await approveLead(id)
    if (result.success) {
      loadLead()
    } else {
      setActionError(result.error)
    }
  }

  const handleReject = async () => {
    setActionError(null)
    const result = await rejectLead(id)
    if (result.success) {
      loadLead()
    } else {
      setActionError(result.error)
    }
  }

  if (loading) return <div className="loading">Loading...</div>
  if (error) return <div className="error">Failed to load: {error}</div>
  if (!data?.lead) return <div className="error">Lead not found</div>

  const { lead, action_history } = data

  return (
    <div>
      <Link to="/leads" className="back-link">← Back to Leads</Link>
      <h1 className="page-title">{lead.business_name}</h1>
      
      {actionError && <div className="error">Action failed: {actionError}</div>}

      {/* Review Actions */}
      <div className="card review-actions-card">
        <div className="card-header">Review Status</div>
        <div className="card-body">
          <div className="review-status-display">
            <span className={`review-status large ${lead.review_status}`}>
              {lead.review_status?.toUpperCase()}
            </span>
            
            <div className="review-buttons">
              {lead.review_status === 'pending' && (
                <>
                  <button className="btn-approve" onClick={handleApprove}>
                    ✓ Approve for Outreach
                  </button>
                  <button className="btn-reject" onClick={handleReject}>
                    ✗ Reject
                  </button>
                </>
              )}
              {lead.review_status === 'approved' && (
                <button className="btn-reject" onClick={handleReject}>
                  ✗ Reject (Remove from Outreach)
                </button>
              )}
              {lead.review_status === 'rejected' && (
                <button className="btn-approve" onClick={handleApprove}>
                  ✓ Approve for Outreach
                </button>
              )}
            </div>
          </div>
          
          {lead.review_status === 'approved' && lead.outreach_status === 'not_sent' && (
            <p className="status-note">This lead will receive emails when outreach is started.</p>
          )}
          {lead.review_status === 'rejected' && (
            <p className="status-note">This lead will NOT receive any emails.</p>
          )}
        </div>
      </div>

      {/* Lead Details */}
      <div className="card">
        <div className="card-header">Lead Details</div>
        <div className="card-body">
          <div className="detail-grid">
            <div className="detail-item">
              <div className="label">Lead ID</div>
              <div className="value">{lead.lead_id}</div>
            </div>
            <div className="detail-item">
              <div className="label">Email</div>
              <div className="value">
                {lead.email || <span className="no-email">No email found</span>}
              </div>
            </div>
            <div className="detail-item">
              <div className="label">Category</div>
              <div className="value">{lead.category || '-'}</div>
            </div>
            <div className="detail-item">
              <div className="label">Location</div>
              <div className="value">{lead.location || '-'}</div>
            </div>
            <div className="detail-item">
              <div className="label">Website</div>
              <div className="value">
                {lead.website_url ? (
                  <a href={lead.website_url} target="_blank" rel="noopener noreferrer">
                    {lead.website_url}
                  </a>
                ) : '-'}
              </div>
            </div>
            <div className="detail-item">
              <div className="label">Maps URL</div>
              <div className="value">
                {lead.maps_url ? (
                  <a href={lead.maps_url} target="_blank" rel="noopener noreferrer">
                    View on Maps
                  </a>
                ) : '-'}
              </div>
            </div>
            <div className="detail-item">
              <div className="label">Tag</div>
              <div className="value">
                {lead.tag ? <span className="tag">{lead.tag}</span> : '-'}
              </div>
            </div>
            <div className="detail-item">
              <div className="label">Discovery Source</div>
              <div className="value">{lead.discovery_source || '-'}</div>
            </div>
            <div className="detail-item">
              <div className="label">Discovery Confidence</div>
              <div className="value">{lead.discovery_confidence || '-'}</div>
            </div>
            <div className="detail-item">
              <div className="label">Outreach Status</div>
              <div className="value">
                <span className={`outreach-status ${lead.outreach_status}`}>
                  {lead.outreach_status?.replace('_', ' ')}
                </span>
              </div>
            </div>
            <div className="detail-item">
              <div className="label">Discovered At</div>
              <div className="value">
                {lead.discovered_at ? new Date(lead.discovered_at).toLocaleString() : '-'}
              </div>
            </div>
            <div className="detail-item">
              <div className="label">Last Contacted</div>
              <div className="value">
                {lead.last_contacted ? new Date(lead.last_contacted).toLocaleString() : '-'}
              </div>
            </div>
            {lead.notes && (
              <div className="detail-item full-width">
                <div className="label">Notes</div>
                <div className="value">{lead.notes}</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Action History */}
      <div className="card">
        <div className="card-header">Action History</div>
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Module</th>
              <th>Action</th>
              <th>Result</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {action_history?.map((log, i) => (
              <tr key={i}>
                <td>{new Date(log.timestamp).toLocaleString()}</td>
                <td>{log.module}</td>
                <td>{log.action}</td>
                <td>
                  <span className={`result-badge ${log.result}`}>{log.result}</span>
                </td>
                <td className="details-cell">{log.details || '-'}</td>
              </tr>
            ))}
            {(!action_history || action_history.length === 0) && (
              <tr>
                <td colSpan="5" className="empty-state">No actions recorded yet</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
