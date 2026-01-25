import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getLeadDetail, approveLead, getEnrichmentData, getLeadScore } from '../api'

export default function LeadDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [lead, setLead] = useState(null)
  const [enrichment, setEnrichment] = useState(null)
  const [score, setScore] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadLead()
  }, [id])

  async function loadLead() {
    setLoading(true)
    const { data: leadData } = await getLeadDetail(id)
    if (leadData) {
      setLead(leadData)
      // Parallel load extra data
      getEnrichmentData(id).then(res => setEnrichment(res.data))
      getLeadScore(id).then(res => setScore(res.data))
    }
    setLoading(false)
  }

  const handleApprove = async () => {
    await approveLead(id)
    loadLead()
  }

  if (loading) return <div className="loading">Loading profile...</div>
  if (!lead) return <div>Lead not found</div>

  return (
    <div className="animate-fade-in" style={{ paddingBottom: '40px' }}>
      {/* Header Profile */}
      <div className="card" style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', gap: '24px' }}>
          <div style={{
            width: '80px', height: '80px',
            background: 'linear-gradient(135deg, var(--bg-hover), var(--bg-card))',
            borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '24px', fontWeight: 'bold', border: '1px solid var(--border-subtle)'
          }}>
            {lead.business_name.substring(0, 2).toUpperCase()}
          </div>
          <div>
            <h1 style={{ fontSize: '24px', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '12px' }}>
              {lead.business_name}
              <span className={`badge ${lead.review_status}`}>{lead.review_status}</span>
            </h1>
            <div style={{ display: 'flex', gap: '16px', color: 'var(--text-secondary)', fontSize: '14px' }}>
              {lead.website_url && (
                <a href={lead.website_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-info)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                  Website
                </a>
              )}
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                {lead.location}
              </span>
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn btn-secondary">Edit</button>
          {lead.review_status !== 'approved' && (
            <button className="btn btn-primary" onClick={handleApprove}>Approve for Outreach</button>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
        {/* Left Column - Details */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Contact Info */}
          <div className="card">
            <h3>Contact Information</h3>
            <div className="dashboard-grid" style={{ gridTemplateColumns: '1fr 1fr', margin: 0, gap: '16px' }}>
              <div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Email</div>
                <div style={{ fontSize: '15px' }}>{lead.email || 'Not found'}</div>
              </div>
              <div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Phone</div>
                <div style={{ fontSize: '15px' }}>{lead.phone || 'Not found'}</div>
              </div>
            </div>
          </div>

          {/* AI Analysis / Enrichment */}
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3>AI Intelligence</h3>
              {enrichment && <span className="badge discovered">Enriched</span>}
            </div>

            {!enrichment ? (
              <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-secondary)', background: 'var(--bg-panel)', borderRadius: '8px' }}>
                Enrichment in progress...
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Tech Stack</div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '4px' }}>
                    {(enrichment.technologies || ['React', 'Node.js', 'AWS']).map(tech => (
                      <span key={tech} style={{ padding: '2px 8px', background: 'var(--bg-hover)', borderRadius: '4px', fontSize: '12px', border: '1px solid var(--border-subtle)' }}>
                        {tech}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Estimated Revenue</div>
                  <div>{enrichment.revenue_range || '$1M - $5M'}</div>
                </div>
              </div>
            )}
          </div>

          {/* Timeline / Activity */}
          <div className="card">
            <h3>Activity Timeline</h3>
            <div style={{ marginTop: '16px', borderLeft: '2px solid var(--border-subtle)', paddingLeft: '20px', marginLeft: '8px' }}>
              <div style={{ position: 'relative', paddingBottom: '24px' }}>
                <div style={{ position: 'absolute', left: '-25px', top: '4px', width: '10px', height: '10px', borderRadius: '50%', background: 'var(--accent-info)', border: '2px solid var(--bg-card)' }}></div>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Today, 2:30 PM</div>
                <div>Lead Approved for Outreach</div>
              </div>
              <div style={{ position: 'relative', paddingBottom: '24px' }}>
                <div style={{ position: 'absolute', left: '-25px', top: '4px', width: '10px', height: '10px', borderRadius: '50%', background: 'var(--text-tertiary)', border: '2px solid var(--bg-card)' }}></div>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Yesterday</div>
                <div>Discovered via Google Maps (Low Confidence)</div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column - Scoring & Actions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Lead Score */}
          <div className="card">
            <h3>Lead Score</h3>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '24px 0' }}>
              <div style={{
                width: '120px', height: '120px', borderRadius: '50%',
                border: '8px solid var(--bg-hover)', borderTopColor: 'var(--accent-primary)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '32px', fontWeight: 'bold'
              }}>
                {Math.round((lead.quality_score || 0) * 100)}
              </div>
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)', textAlign: 'center' }}>
              Based on location, industry match, and digital presence.
            </div>
          </div>

          {/* Quick Notes */}
          <div className="card">
            <h3>Notes</h3>
            <textarea
              className="input-field"
              rows="6"
              placeholder="Add notes about this lead..."
              defaultValue={lead.notes}
              style={{ marginTop: '12px', resize: 'vertical' }}
            ></textarea>
            <div style={{ marginTop: '12px', textAlign: 'right' }}>
              <button className="btn btn-secondary" style={{ fontSize: '12px' }}>Save Note</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
