import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Mail, MessageSquare, Activity, RefreshCw, Check, X, Loader2 } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { formatDateTime, getRelativeTime } from '@/lib/utils';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

// API calls
const fetchLeadDetail = async (leadId: string) => {
  const response = await axios.get(`${API_BASE_URL}/api/leads/${leadId}`);
  return response.data;
};

const approveLead = async (leadId: string) => {
  const response = await axios.post(`${API_BASE_URL}/api/leads/${leadId}/approve`);
  return response.data;
};

const rejectLead = async (leadId: string) => {
  const response = await axios.post(`${API_BASE_URL}/api/leads/${leadId}/reject`);
  return response.data;
};

const getReviewStatusBadgeVariant = (status: string) => {
  switch (status) {
    case 'approved':
      return 'success';
    case 'rejected':
      return 'error';
    case 'pending':
      return 'warning';
    default:
      return 'neutral';
  }
};

const getOutreachStatusBadgeVariant = (status: string) => {
  switch (status) {
    case 'sent_initial':
    case 'sent_followup':
      return 'success';
    case 'replied':
      return 'success';
    case 'not_sent':
      return 'neutral';
    default:
      return 'neutral';
  }
};

const getHistoryIcon = (type: string) => {
  switch (type) {
    case 'email_sent':
    case 'send_initial':
    case 'send_followup':
      return Mail;
    case 'reply_received':
    case 'detect_reply':
      return MessageSquare;
    case 'status_change':
    case 'approve':
    case 'reject':
      return RefreshCw;
    default:
      return Activity;
  }
};

const getHistoryTypeLabel = (action: string) => {
  switch (action) {
    case 'send_initial':
      return 'Initial Email Sent';
    case 'send_followup':
      return 'Follow-up Sent';
    case 'detect_reply':
      return 'Reply Detected';
    case 'approve':
      return 'Lead Approved';
    case 'reject':
      return 'Lead Rejected';
    case 'discover_one':
      return 'Lead Discovered';
    case 'analyze':
      return 'Website Analyzed';
    default:
      return action.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  }
};

const getResultBadgeVariant = (result: string) => {
  switch (result) {
    case 'success':
      return 'success';
    case 'error':
      return 'error';
    case 'blocked':
    case 'skipped':
      return 'warning';
    default:
      return 'neutral';
  }
};

export default function LeadDetail() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ['leadDetail', id],
    queryFn: () => fetchLeadDetail(id!),
    enabled: !!id,
    refetchInterval: 10000 // Refresh every 10 seconds
  });

  const approveMutation = useMutation({
    mutationFn: () => approveLead(id!),
    onSuccess: (data) => {
      toast.success('Lead approved successfully');
      queryClient.invalidateQueries({ queryKey: ['leadDetail', id] });
      queryClient.invalidateQueries({ queryKey: ['leads'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
    },
    onError: (error: any) => {
      toast.error(`Failed to approve lead: ${error.response?.data?.detail || error.message}`);
    }
  });

  const rejectMutation = useMutation({
    mutationFn: () => rejectLead(id!),
    onSuccess: (data) => {
      toast.success('Lead rejected successfully');
      queryClient.invalidateQueries({ queryKey: ['leadDetail', id] });
      queryClient.invalidateQueries({ queryKey: ['leads'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
    },
    onError: (error: any) => {
      toast.error(`Failed to reject lead: ${error.response?.data?.detail || error.message}`);
    }
  });

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="p-6 flex items-center justify-center min-h-[50vh]">
          <div className="text-center">
            <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto mb-2" />
            <p className="text-muted-foreground">Loading lead details...</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !data?.lead) {
    return (
      <DashboardLayout>
        <div className="p-6">
          <Link
            to="/leads"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to leads
          </Link>
          <div className="text-center py-12">
            <p className="text-muted-foreground">
              {error ? `Error: ${(error as Error).message}` : 'Lead not found'}
            </p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  const { lead, action_history } = data;

  return (
    <DashboardLayout>
      <div className="p-6">
        <Link
          to="/leads"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to leads
        </Link>

        {/* Lead Header */}
        <div className="bg-card border border-border rounded-lg p-6 mb-6">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-xl font-semibold text-foreground">
                {lead.business_name}
              </h1>
              <p className="text-sm text-muted-foreground mt-1">
                {lead.email || 'No email found'}
              </p>
              {lead.website_url && (
                <a
                  href={lead.website_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline mt-1 block"
                >
                  {lead.website_url}
                </a>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={getReviewStatusBadgeVariant(lead.review_status)}>
                {lead.review_status}
              </Badge>
              <Badge variant={getOutreachStatusBadgeVariant(lead.outreach_status)}>
                {lead.outreach_status}
              </Badge>
            </div>
          </div>

          {/* Action Buttons */}
          {lead.review_status === 'pending' && (
            <div className="flex gap-2 mt-4 pt-4 border-t border-border">
              <Button
                onClick={() => approveMutation.mutate()}
                disabled={approveMutation.isPending || !lead.email}
                className="bg-green-600 hover:bg-green-700"
              >
                {approveMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Check className="h-4 w-4 mr-2" />
                )}
                Approve for Outreach
              </Button>
              <Button
                variant="destructive"
                onClick={() => rejectMutation.mutate()}
                disabled={rejectMutation.isPending}
              >
                {rejectMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <X className="h-4 w-4 mr-2" />
                )}
                Reject
              </Button>
              {!lead.email && (
                <span className="text-sm text-muted-foreground self-center ml-2">
                  (Cannot approve without email)
                </span>
              )}
            </div>
          )}

          {lead.review_status === 'approved' && lead.outreach_status === 'not_sent' && (
            <div className="mt-4 pt-4 border-t border-border">
              <p className="text-sm text-muted-foreground">
                ✓ Lead approved. Will receive email when outreach is started.
              </p>
            </div>
          )}

          <div className="grid grid-cols-4 gap-6 mt-6 pt-6 border-t border-border">
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Category
              </p>
              <p className="text-sm mt-1">{lead.category || 'Unknown'}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Tag
              </p>
              <p className="text-sm mt-1">
                <Badge variant="neutral">{lead.tag || 'None'}</Badge>
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Discovered
              </p>
              <p className="text-sm mt-1 font-mono">
                {lead.discovered_at ? formatDateTime(lead.discovered_at) : 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Last Contacted
              </p>
              <p className="text-sm mt-1 font-mono">
                {lead.last_contacted ? formatDateTime(lead.last_contacted) : 'Never'}
              </p>
            </div>
          </div>

          {/* Additional Info */}
          <div className="grid grid-cols-2 gap-6 mt-4 pt-4 border-t border-border">
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Location
              </p>
              <p className="text-sm mt-1">{lead.location || 'Unknown'}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Discovery Source
              </p>
              <p className="text-sm mt-1">{lead.discovery_source || 'Unknown'}</p>
            </div>
          </div>

          {lead.maps_url && (
            <div className="mt-4 pt-4 border-t border-border">
              <a
                href={lead.maps_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline"
              >
                View on Google Maps →
              </a>
            </div>
          )}
        </div>

        {/* History */}
        <div>
          <h2 className="text-sm font-semibold text-foreground mb-4">
            Activity History
          </h2>

          {!action_history || action_history.length === 0 ? (
            <div className="bg-card border border-border rounded-lg p-8 text-center">
              <p className="text-muted-foreground">No activity history available</p>
            </div>
          ) : (
            <div className="space-y-4">
              {action_history.map((item: any) => {
                const Icon = getHistoryIcon(item.action);

                return (
                  <div
                    key={item.id}
                    className="bg-card border border-border rounded-lg p-4"
                  >
                    <div className="flex items-start gap-3">
                      <div className="p-2 bg-secondary rounded">
                        <Icon className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium">
                              {getHistoryTypeLabel(item.action)}
                            </span>
                            <Badge variant="neutral" className="text-xs">
                              {item.module}
                            </Badge>
                            <Badge variant={getResultBadgeVariant(item.result)} className="text-xs">
                              {item.result}
                            </Badge>
                          </div>
                          <span className="text-xs text-muted-foreground font-mono">
                            {item.timestamp ? getRelativeTime(item.timestamp) : ''}
                          </span>
                        </div>

                        {item.details && (
                          <p className="mt-2 text-sm text-muted-foreground">
                            {typeof item.details === 'string'
                              ? item.details
                              : JSON.stringify(item.details)}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
