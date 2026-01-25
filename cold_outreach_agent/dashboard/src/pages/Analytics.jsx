import { useState, useEffect } from 'react'
import { getAnalyticsDashboard } from '../api'

// Simple CSS Bar Chart Component
const SimpleBarChart = ({ data, color = 'var(--accent-info)' }) => {
    const max = Math.max(...data.map(d => d.value));
    return (
        <div style={{ display: 'flex', alignItems: 'flex-end', height: '150px', gap: '8px', paddingTop: '20px' }}>
            {data.map((d, i) => (
                <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <div
                        style={{
                            width: '100%',
                            height: `${(d.value / max) * 100}%`,
                            background: color,
                            borderRadius: '4px 4px 0 0',
                            opacity: 0.8,
                            transition: 'height 0.5s ease',
                            minHeight: '4px'
                        }}
                    />
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '6px' }}>{d.label}</span>
                </div>
            ))}
        </div>
    )
}

export default function Analytics() {
    const [data, setData] = useState(null)

    useEffect(() => {
        loadData()
    }, [])

    async function loadData() {
        const { data: analytics } = await getAnalyticsDashboard()
        if (analytics) setData(analytics)
        // Fallback mock data for demo if API returns empty
        else setData({
            total_leads: 1243,
            new_leads_this_week: 156,
            total_emails_sent: 892,
            emails_sent_this_week: 145,
            open_rate: 42.5,
            reply_rate: 12.8,
            avg_emails_per_day: 24
        })
    }

    if (!data) return <div className="loading">Loading analytics...</div>

    // Mock trend data for charts
    const weeklyLeads = [
        { label: 'Mon', value: 12 }, { label: 'Tue', value: 18 }, { label: 'Wed', value: 25 },
        { label: 'Thu', value: 22 }, { label: 'Fri', value: 30 }, { label: 'Sat', value: 15 }, { label: 'Sun', value: 10 }
    ];

    const weeklyEmails = [
        { label: 'Mon', value: 45 }, { label: 'Tue', value: 52 }, { label: 'Wed', value: 48 },
        { label: 'Thu', value: 60 }, { label: 'Fri', value: 55 }, { label: 'Sat', value: 20 }, { label: 'Sun', value: 15 }
    ];

    return (
        <div className="animate-fade-in">
            {/* KPI Cards */}
            <div className="dashboard-grid">
                <div className="card">
                    <h3>Total Leads</h3>
                    <div className="metric-value">{data.total_leads.toLocaleString()}</div>
                    <div className="metric-trend trend-up">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>
                        +{data.new_leads_this_week} this week
                    </div>
                </div>

                <div className="card">
                    <h3>Response Rate</h3>
                    <div className="metric-value">{data.reply_rate}%</div>
                    <div className="metric-trend trend-up">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>
                        +2.1% vs last week
                    </div>
                </div>

                <div className="card">
                    <h3>Emails Sent</h3>
                    <div className="metric-value">{data.total_emails_sent.toLocaleString()}</div>
                    <div className="metric-trend">
                        {data.avg_emails_per_day} avg daily
                    </div>
                </div>

                <div className="card">
                    <h3>Open Rate</h3>
                    <div className="metric-value">{data.open_rate}%</div>
                    <div className="metric-trend trend-up">
                        Top 15% industry
                    </div>
                </div>
            </div>

            {/* Charts Row */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '32px' }}>
                <div className="card">
                    <h3>Lead Acquisition Trend</h3>
                    <SimpleBarChart data={weeklyLeads} color="var(--accent-purple)" />
                </div>
                <div className="card">
                    <h3>Outreach Volume</h3>
                    <SimpleBarChart data={weeklyEmails} color="var(--accent-info)" />
                </div>
            </div>

            {/* Heatmap / Top Section */}
            <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
                    <h3>Top Performing Industries</h3>
                    <button className="btn btn-secondary" style={{ fontSize: '12px', padding: '4px 8px' }}>View Full Report</button>
                </div>
                <table className="data-table">
                    <thead>
                        <tr>
                            <th>Industry</th>
                            <th>Leads</th>
                            <th>Response Rate</th>
                            <th>Conversion</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>SaaS / Software</td>
                            <td>452</td>
                            <td>18.5%</td>
                            <td><span className="badge approved">High</span></td>
                        </tr>
                        <tr>
                            <td>Marketing Agencies</td>
                            <td>284</td>
                            <td>14.2%</td>
                            <td><span className="badge discovered">Medium</span></td>
                        </tr>
                        <tr>
                            <td>E-commerce</td>
                            <td>195</td>
                            <td>8.4%</td>
                            <td><span className="badge pending">Low</span></td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    )
}
