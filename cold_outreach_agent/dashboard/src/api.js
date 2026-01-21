const API_URL = import.meta.env.VITE_API_URL || '';

let lastKnownData = {
  overview: null,
  leads: null,
  logs: null,
  system: null,
  agentState: null
};

async function fetchWithFallback(endpoint, cacheKey) {
  try {
    const res = await fetch(`${API_URL}${endpoint}`, {
      signal: AbortSignal.timeout(5000)
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    lastKnownData[cacheKey] = data;
    return { data, stale: false, error: null };
  } catch (err) {
    if (lastKnownData[cacheKey]) {
      return { data: lastKnownData[cacheKey], stale: true, error: err.message };
    }
    return { data: null, stale: false, error: err.message };
  }
}

// --- Read Endpoints ---

export async function getOverview() {
  return fetchWithFallback('/api/overview', 'overview');
}

export async function getLeads(filters = {}) {
  const params = new URLSearchParams();
  if (filters.review_status) params.set('review_status', filters.review_status);
  if (filters.outreach_status) params.set('outreach_status', filters.outreach_status);
  const query = params.toString() ? `?${params}` : '';
  return fetchWithFallback(`/api/leads${query}`, 'leads');
}

export async function getLeadDetail(leadId) {
  try {
    const res = await fetch(`${API_URL}/api/leads/${leadId}`, {
      signal: AbortSignal.timeout(5000)
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { data: await res.json(), error: null };
  } catch (err) {
    return { data: null, error: err.message };
  }
}

export async function getLogs(filters = {}) {
  const params = new URLSearchParams();
  if (filters.module) params.set('module', filters.module);
  if (filters.lead_id) params.set('lead_id', filters.lead_id);
  if (filters.limit) params.set('limit', filters.limit);
  const query = params.toString() ? `?${params}` : '';
  return fetchWithFallback(`/api/logs${query}`, 'logs');
}

export async function getSystem() {
  return fetchWithFallback('/api/system', 'system');
}

export async function getAgentState() {
  return fetchWithFallback('/api/agent/state', 'agentState');
}

export async function getControlLogs(limit = 50) {
  const params = new URLSearchParams({ limit: limit.toString() });
  return fetchWithFallback(`/api/agent/control-logs?${params}`, 'controlLogs');
}

// --- Agent Control ---

async function postAgentControl(endpoint, body = null) {
  try {
    const options = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(10000)
    };
    if (body) options.body = JSON.stringify(body);
    
    const res = await fetch(`${API_URL}${endpoint}`, options);
    const data = await res.json();
    
    if (!res.ok) {
      return { 
        success: false, 
        error: data.detail || `HTTP ${res.status}`,
        state: data.state || null
      };
    }
    
    return { 
      success: true, 
      message: data.message,
      state: data.state,
      error: null 
    };
  } catch (err) {
    return { success: false, error: err.message, state: null };
  }
}

// Discovery Control
export async function startDiscovery(query, location, maxResults = 50) {
  return postAgentControl('/api/agent/discover/start', { query, location, max_results: maxResults });
}

export async function stopDiscovery() {
  return postAgentControl('/api/agent/discover/stop');
}

// Outreach Control
export async function startOutreach() {
  return postAgentControl('/api/agent/outreach/start');
}

export async function stopOutreach() {
  return postAgentControl('/api/agent/outreach/stop');
}

// Common Controls
export async function pauseAgent() {
  return postAgentControl('/api/agent/pause');
}

export async function resumeAgent() {
  return postAgentControl('/api/agent/resume');
}

export async function stopAgent() {
  return postAgentControl('/api/agent/stop');
}

export async function resetAgent() {
  return postAgentControl('/api/agent/reset');
}

// --- Lead Review Actions ---

export async function approveLead(leadId) {
  return postAgentControl(`/api/leads/${leadId}/approve`);
}

export async function rejectLead(leadId) {
  return postAgentControl(`/api/leads/${leadId}/reject`);
}

export async function bulkApproveLeads(leadIds) {
  return postAgentControl('/api/leads/bulk-approve', { lead_ids: leadIds });
}

export async function bulkRejectLeads(leadIds) {
  return postAgentControl('/api/leads/bulk-reject', { lead_ids: leadIds });
}
