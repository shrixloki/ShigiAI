import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { DataTable } from '@/components/dashboard/DataTable';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { formatDateTime } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { Check, X, Loader2 } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

// API calls for bulk actions
const bulkApproveLeads = async (leadIds: string[]) => {
  const response = await axios.post(`${API_BASE_URL}/api/leads/bulk-approve`, { lead_ids: leadIds });
  return response.data;
};

const bulkRejectLeads = async (leadIds: string[]) => {
  const response = await axios.post(`${API_BASE_URL}/api/leads/bulk-reject`, { lead_ids: leadIds });
  return response.data;
};

const clearAllLeads = async () => {
  const response = await axios.delete(`${API_BASE_URL}/api/leads/clear-all`);
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

const reviewStatusFilters = ['All', 'pending', 'approved', 'rejected'] as const;
const outreachStatusFilters = ['All', 'not_sent', 'sent_initial', 'sent_followup', 'replied'] as const;

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

interface Lead {
  lead_id: string;
  business_name: string;
  category: string;
  location: string;
  email: string;
  website_url: string;
  tag: string;
  review_status: string;
  outreach_status: string;
  discovered_at: string;
  last_contacted: string;
}

export default function Leads() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [reviewStatusFilter, setReviewStatusFilter] = useState<string>('All');
  const [outreachStatusFilter, setOutreachStatusFilter] = useState<string>('All');
  const [selectedLeads, setSelectedLeads] = useState<Set<string>>(new Set());

  // Fetch leads from API
  const { data: leads = [], isLoading } = useQuery({
    queryKey: ['leads'],
    queryFn: () => api.getLeads(),
    refetchInterval: 5000
  });

  // Bulk approve mutation
  const bulkApproveMutation = useMutation({
    mutationFn: bulkApproveLeads,
    onSuccess: (data) => {
      toast.success(`Approved ${data.approved_count} leads`);
      setSelectedLeads(new Set());
      queryClient.invalidateQueries({ queryKey: ['leads'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
    },
    onError: (error: any) => {
      toast.error(`Failed to approve leads: ${error.message}`);
    }
  });

  // Bulk reject mutation
  const bulkRejectMutation = useMutation({
    mutationFn: bulkRejectLeads,
    onSuccess: (data) => {
      toast.success(`Rejected ${data.rejected_count} leads`);
      setSelectedLeads(new Set());
      queryClient.invalidateQueries({ queryKey: ['leads'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
    },
    onError: (error: any) => {
      toast.error(`Failed to reject leads: ${error.message}`);
    }
  });

  // Single lead approve mutation
  const approveMutation = useMutation({
    mutationFn: approveLead,
    onSuccess: (data) => {
      toast.success('Lead approved');
      queryClient.invalidateQueries({ queryKey: ['leads'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
    },
    onError: (error: any) => {
      toast.error(`Failed to approve: ${error.response?.data?.detail || error.message}`);
    }
  });

  // Single lead reject mutation
  const rejectMutation = useMutation({
    mutationFn: rejectLead,
    onSuccess: (data) => {
      toast.success('Lead rejected');
      queryClient.invalidateQueries({ queryKey: ['leads'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
    },
    onError: (error: any) => {
      toast.error(`Failed to reject: ${error.response?.data?.detail || error.message}`);
    }
  });

  const filteredLeads = useMemo(() => {
    if (!Array.isArray(leads)) return [];
    let filtered = [...leads];

    if (reviewStatusFilter !== 'All') {
      filtered = filtered.filter((lead) => lead.review_status === reviewStatusFilter);
    }

    if (outreachStatusFilter !== 'All') {
      filtered = filtered.filter((lead) => lead.outreach_status === outreachStatusFilter);
    }

    return filtered;
  }, [leads, reviewStatusFilter, outreachStatusFilter]);

  const resetFilters = () => {
    setReviewStatusFilter('All');
    setOutreachStatusFilter('All');
  };

  const handleRowClick = (lead: Lead) => {
    navigate(`/leads/${lead.lead_id}`);
  };

  const handleSelectLead = (leadId: string, checked: boolean) => {
    const newSelected = new Set(selectedLeads);
    if (checked) {
      newSelected.add(leadId);
    } else {
      newSelected.delete(leadId);
    }
    setSelectedLeads(newSelected);
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const pendingLeads = filteredLeads.filter(l => l.review_status === 'pending');
      setSelectedLeads(new Set(pendingLeads.map(l => l.lead_id)));
    } else {
      setSelectedLeads(new Set());
    }
  };

  const pendingLeadsInView = filteredLeads.filter(l => l.review_status === 'pending');
  const allPendingSelected = pendingLeadsInView.length > 0 &&
    pendingLeadsInView.every(l => selectedLeads.has(l.lead_id));

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="p-6">
          <PageHeader title="Leads" description="Manage and review discovered leads" />
          <div className="space-y-4 mt-6">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-6">
        <PageHeader
          title="Leads"
          description="Manage and review discovered leads"
        />

        {/* Bulk Actions */}
        {selectedLeads.size > 0 && (
          <div className="flex items-center gap-3 mb-4 p-3 bg-secondary rounded-lg">
            <span className="text-sm font-medium">{selectedLeads.size} leads selected</span>
            <Button
              size="sm"
              onClick={() => bulkApproveMutation.mutate(Array.from(selectedLeads))}
              disabled={bulkApproveMutation.isPending}
              className="bg-green-600 hover:bg-green-700"
            >
              {bulkApproveMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin mr-1" />
              ) : (
                <Check className="h-4 w-4 mr-1" />
              )}
              Approve All
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => bulkRejectMutation.mutate(Array.from(selectedLeads))}
              disabled={bulkRejectMutation.isPending}
            >
              {bulkRejectMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin mr-1" />
              ) : (
                <X className="h-4 w-4 mr-1" />
              )}
              Reject All
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setSelectedLeads(new Set())}
            >
              Clear Selection
            </Button>
          </div>
        )}

        {/* Filters */}
        <div className="flex items-center gap-3 mb-6">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Review:</span>
            <Select value={reviewStatusFilter} onValueChange={setReviewStatusFilter}>
              <SelectTrigger className="w-28 h-8 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {reviewStatusFilters.map((status) => (
                  <SelectItem key={status} value={status}>
                    {status === 'All' ? 'All' : status}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Outreach:</span>
            <Select value={outreachStatusFilter} onValueChange={setOutreachStatusFilter}>
              <SelectTrigger className="w-32 h-8 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {outreachStatusFilters.map((status) => (
                  <SelectItem key={status} value={status}>
                    {status === 'All' ? 'All' : status.replace(/_/g, ' ')}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {(reviewStatusFilter !== 'All' || outreachStatusFilter !== 'All') && (
            <Button
              variant="ghost"
              size="sm"
              onClick={resetFilters}
              className="text-xs text-muted-foreground"
            >
              Reset filters
            </Button>
          )}

          <span className="ml-auto text-sm text-muted-foreground">
            {filteredLeads.length} leads
          </span>
        </div>

        {/* Table */}
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-secondary/50">
              <tr>
                <th className="px-4 py-3 text-left">
                  <Checkbox
                    checked={allPendingSelected}
                    onCheckedChange={handleSelectAll}
                    disabled={pendingLeadsInView.length === 0}
                  />
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Business</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Email</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Tag</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Review</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Outreach</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Location</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredLeads.map((lead) => (
                <tr
                  key={lead.lead_id}
                  className="hover:bg-secondary/30 transition-colors"
                >
                  <td className="px-4 py-3">
                    {lead.review_status === 'pending' && (
                      <Checkbox
                        checked={selectedLeads.has(lead.lead_id)}
                        onCheckedChange={(checked) => handleSelectLead(lead.lead_id, checked as boolean)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    )}
                  </td>
                  <td
                    className="px-4 py-3 cursor-pointer"
                    onClick={() => handleRowClick(lead)}
                  >
                    <span className="font-medium hover:underline">{lead.business_name}</span>
                    {lead.category && (
                      <span className="block text-xs text-muted-foreground">{lead.category}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {lead.email || <span className="text-muted-foreground italic">No email</span>}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant="neutral">{lead.tag || 'unknown'}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={getReviewStatusBadgeVariant(lead.review_status)}>
                      {lead.review_status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={getOutreachStatusBadgeVariant(lead.outreach_status)}>
                      {lead.outreach_status.replace(/_/g, ' ')}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {lead.location || 'Unknown'}
                  </td>
                  <td className="px-4 py-3">
                    {lead.review_status === 'pending' && (
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 w-7 p-0 text-green-600 hover:text-green-700 hover:bg-green-50"
                          onClick={(e) => {
                            e.stopPropagation();
                            approveMutation.mutate(lead.lead_id);
                          }}
                          disabled={!lead.email || approveMutation.isPending}
                          title={lead.email ? 'Approve' : 'Cannot approve without email'}
                        >
                          <Check className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 w-7 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                          onClick={(e) => {
                            e.stopPropagation();
                            rejectMutation.mutate(lead.lead_id);
                          }}
                          disabled={rejectMutation.isPending}
                          title="Reject"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {filteredLeads.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                    No leads match your filters
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardLayout>
  );
}
