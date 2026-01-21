import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

// Create axios instance with defaults
const apiClient = axios.create({
    baseURL: API_BASE_URL,
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json',
    }
});

export interface DashboardStats {
    total_leads: number;
    pending_review: number;
    approved: number;
    rejected: number;
    emails_sent_today: number;
    sent_initial: number;
    sent_followup: number;
    replies_received: number;
}

export interface Lead {
    lead_id: string;
    business_name: string;
    category: string;
    location: string;
    maps_url: string;
    website_url: string;
    email: string;
    tag: string;
    review_status: string;
    outreach_status: string;
    discovery_source: string;
    discovered_at: string;
    last_contacted: string;
}

export interface LeadDetail {
    lead: Lead;
    action_history: ActivityLog[];
}

export interface ActivityLog {
    id: number;
    timestamp: string;
    lead_id: string;
    module: string;
    action: string;
    result: string;
    details: string;
}

export interface SystemHealth {
    agent_state: string;
    last_transition_time: string;
    last_heartbeat: string;
    current_task: string;
    discovery_query: string;
    discovery_location: string;
    is_healthy: boolean;
    health_reason: string;
    error_message: string;
    error_count_24h: number;
    emails_sent_today: number;
    email_quota: number;
    lead_counts: {
        total: number;
        pending_review: number;
        approved: number;
        rejected: number;
        replied: number;
    };
}

export interface AgentControlResponse {
    success: boolean;
    message: string;
    state: string;
}

export interface EmailTemplate {
    name: string;
    subject_template: string;
    text_template: string;
    category: string;
    type: 'default' | 'custom';
    variables: string[];
}

export const api = {
    // Dashboard stats
    getOverview: async (): Promise<DashboardStats> => {
        const response = await apiClient.get('/api/overview');
        return response.data;
    },

    // Leads
    getLeads: async (params?: { review_status?: string; outreach_status?: string }): Promise<Lead[]> => {
        const response = await apiClient.get('/api/leads', { params });
        return response.data;
    },

    getLeadDetail: async (leadId: string): Promise<LeadDetail> => {
        const response = await apiClient.get(`/api/leads/${leadId}`);
        return response.data;
    },

    approveLead: async (leadId: string): Promise<{ success: boolean; lead_id: string; review_status: string }> => {
        const response = await apiClient.post(`/api/leads/${leadId}/approve`);
        return response.data;
    },

    rejectLead: async (leadId: string): Promise<{ success: boolean; lead_id: string; review_status: string }> => {
        const response = await apiClient.post(`/api/leads/${leadId}/reject`);
        return response.data;
    },

    bulkApproveLeads: async (leadIds: string[]): Promise<{ success: boolean; approved_count: number }> => {
        const response = await apiClient.post('/api/leads/bulk-approve', { lead_ids: leadIds });
        return response.data;
    },

    bulkRejectLeads: async (leadIds: string[]): Promise<{ success: boolean; rejected_count: number }> => {
        const response = await apiClient.post('/api/leads/bulk-reject', { lead_ids: leadIds });
        return response.data;
    },

    // Logs
    getLogs: async (params?: { module?: string; lead_id?: string; limit?: number }): Promise<{ logs: ActivityLog[]; total: number }> => {
        const response = await apiClient.get('/api/logs', { params });
        return response.data;
    },

    // System
    getSystemStatus: async (): Promise<SystemHealth> => {
        const response = await apiClient.get('/api/system');
        return response.data;
    },

    getAgentState: async (): Promise<{
        state: string;
        last_transition_time: string;
        reason: string;
        controlled_by: string;
        last_heartbeat: string;
        error_message: string;
        current_task: string;
        discovery_query: string;
        discovery_location: string;
        is_healthy: boolean;
        health_reason: string;
    }> => {
        const response = await apiClient.get('/api/agent/state');
        return response.data;
    },

    getControlLogs: async (limit: number = 50): Promise<{ logs: any[]; total: number }> => {
        const response = await apiClient.get('/api/agent/control-logs', { params: { limit } });
        return response.data;
    },

    // Agent Controls - Discovery
    startDiscovery: async (query: string, location: string, maxResults: number = 50): Promise<AgentControlResponse> => {
        const response = await apiClient.post('/api/agent/discover/start', {
            query,
            location,
            max_results: maxResults
        });
        return response.data;
    },

    stopDiscovery: async (): Promise<AgentControlResponse> => {
        const response = await apiClient.post('/api/agent/discover/stop');
        return response.data;
    },

    // Agent Controls - Outreach
    startOutreach: async (): Promise<AgentControlResponse> => {
        const response = await apiClient.post('/api/agent/outreach/start');
        return response.data;
    },

    stopOutreach: async (): Promise<AgentControlResponse> => {
        const response = await apiClient.post('/api/agent/outreach/stop');
        return response.data;
    },

    // Agent Controls - Common
    pauseAgent: async (): Promise<AgentControlResponse> => {
        const response = await apiClient.post('/api/agent/pause');
        return response.data;
    },

    resumeAgent: async (): Promise<AgentControlResponse> => {
        const response = await apiClient.post('/api/agent/resume');
        return response.data;
    },

    stopAgent: async (): Promise<AgentControlResponse> => {
        const response = await apiClient.post('/api/agent/stop');
        return response.data;
    },

    resetAgent: async (): Promise<AgentControlResponse> => {
        const response = await apiClient.post('/api/agent/reset');
        return response.data;
    },

    // Health check
    healthCheck: async (): Promise<{ status: string; timestamp: string }> => {
        const response = await apiClient.get('/api/health');
        return response.data;
    },

    // Email Templates
    getEmailTemplates: async (): Promise<{ templates: Record<string, EmailTemplate> }> => {
        const response = await apiClient.get('/api/email-templates');
        return response.data;
    },

    getEmailTemplate: async (category: string): Promise<EmailTemplate> => {
        const response = await apiClient.get(`/api/email-templates/${category}`);
        return response.data;
    },

    updateEmailTemplate: async (category: string, subjectTemplate: string, textTemplate: string): Promise<{ success: boolean; message: string; template: EmailTemplate }> => {
        const response = await apiClient.put(`/api/email-templates/${category}`, {
            subject_template: subjectTemplate,
            text_template: textTemplate
        });
        return response.data;
    },

    resetEmailTemplate: async (category: string): Promise<{ success: boolean; message: string }> => {
        const response = await apiClient.delete(`/api/email-templates/${category}`);
        return response.data;
    },

    // Test Email
    sendTestEmail: async (toEmail: string, subject: string, body: string, category?: string): Promise<{ success: boolean; message: string; details: string }> => {
        const response = await apiClient.post('/api/email/test', {
            to_email: toEmail,
            subject,
            body,
            category: category || 'general'
        });
        return response.data;
    }
};
