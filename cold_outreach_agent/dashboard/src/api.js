const API_URL = import.meta.env.VITE_API_URL || '';

let lastKnownData = {
  overview: null,
  leads: null,
  logs: null,
  system: null,
  agentState: null,
  analytics: null,
  enrichment: null
};

async function fetchWithFallback(endpoint, cacheKey, options = {}) {
  try {
    const res = await fetch(`${API_URL}${endpoint}`, {
      signal: AbortSignal.timeout(10000),
      ...options
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.success && data.data) {
      lastKnownData[cacheKey] = data.data;
      return { data: data.data, stale: false, error: null };
    }
    // Handle standard success response wrapper if present, or raw data
    const result = data.data || data;
    lastKnownData[cacheKey] = result;
    return { data: result, stale: false, error: null };
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
  if (filters.lifecycle_state) params.set('lifecycle_state', filters.lifecycle_state);
  if (filters.page) params.set('page', filters.page);
  const query = params.toString() ? `?${params}` : '';
  return fetchWithFallback(`/api/leads${query}`, 'leads');
}

export async function getLeadDetail(leadId) {
  try {
    const res = await fetch(`${API_URL}/api/leads/${leadId}`, {
      signal: AbortSignal.timeout(5000)
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    return { data: json.data || json, error: null };
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
  return fetchWithFallback('/system/status', 'system');
}

// --- New Service Endpoints ---

export async function getAnalyticsDashboard() {
  return fetchWithFallback('/api/analytics/dashboard', 'analytics');
}

export async function getEnrichmentData(leadId) {
  // This triggers enrichment if not present, or gets it
  // For now we assume a POST to trigger
  return postAgentControl(`/api/enrichment/enrich/${leadId}`);
}

export async function getLeadScore(leadId) {
  return fetchWithFallback(`/api/scoring/${leadId}`, `score_${leadId}`);
}

export async function getPublicDirectory(query) {
  const q = query ? `?query=${query}` : '';
  return fetchWithFallback(`/api/public/directory${q}`, 'directory');
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
      data: data.data,
      metadata: data.metadata,
      error: null
    };
  } catch (err) {
    return { success: false, error: err.message, state: null };
  }
}

// Discovery Control
export async function startDiscovery(query, location, maxResults = 50) {
  return postAgentControl('/api/discovery/start', { query, location, max_results: maxResults });
}

// --- Lead Review Actions ---

export async function approveLead(leadId) {
  return postAgentControl(`/api/leads/${leadId}/approve`);
}

export async function bulkApproveLeads(leadIds) {
  return postAgentControl('/api/leads/bulk-approve', { lead_ids: leadIds });
}
