import { useState } from 'react';
import { Mail, MessageSquare, Users, UserCheck, UserX, Loader2, Play, Square, Pause, Search, AlertCircle } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { StatCard } from '@/components/dashboard/StatCard';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { DataTable } from '@/components/dashboard/DataTable';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { getRelativeTime } from '@/lib/utils';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from 'sonner';

const getModuleBadgeVariant = (module: string) => {
  switch (module?.toLowerCase()) {
    case 'scout':
    case 'hunter':
      return 'pending';
    case 'analyst':
    case 'website_analyzer':
      return 'neutral';
    case 'messenger':
      return 'success';
    case 'followup':
    case 'follow-up':
      return 'warning';
    case 'review':
      return 'success';
    default:
      return 'neutral';
  }
};

const getStatusBadgeVariant = (status: string) => {
  switch (status) {
    case 'success':
      return 'success';
    case 'error':
    case 'failed':
      return 'error';
    case 'pending':
    case 'blocked':
    case 'skipped':
      return 'warning';
    default:
      return 'neutral';
  }
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

export default function Index() {
  const queryClient = useQueryClient();
  const [discoveryDialogOpen, setDiscoveryDialogOpen] = useState(false);
  const [discoveryQuery, setDiscoveryQuery] = useState('');
  const [discoveryLocation, setDiscoveryLocation] = useState('');

  const { data: overview, isLoading: statsLoading } = useQuery({
    queryKey: ['overview'],
    queryFn: api.getOverview,
    refetchInterval: 5000
  });

  const { data: logsData, isLoading: logsLoading } = useQuery({
    queryKey: ['recentLogs'],
    queryFn: () => api.getLogs({ limit: 10 }),
    refetchInterval: 3000
  });

  const { data: pendingLeads, isLoading: leadsLoading } = useQuery({
    queryKey: ['pendingLeads'],
    queryFn: () => api.getLeads({ review_status: 'pending' }),
    refetchInterval: 5000
  });

  const { data: systemStatus } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: api.getSystemStatus,
    refetchInterval: 3000
  });

  // Mutations for controls
  const startDiscoveryMutation = useMutation({
    mutationFn: ({ query, location }: { query: string; location: string }) =>
      api.startDiscovery(query, location),
    onSuccess: () => {
      toast.success("Discovery started");
      setDiscoveryDialogOpen(false);
      setDiscoveryQuery('');
      setDiscoveryLocation('');
      queryClient.invalidateQueries({ queryKey: ['systemStatus'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
    },
    onError: (error: any) => {
      toast.error(`Failed to start discovery: ${error.response?.data?.detail || error.message}`);
    }
  });

  const stopDiscoveryMutation = useMutation({
    mutationFn: api.stopDiscovery,
    onSuccess: () => {
      toast.success("Discovery stopped");
      queryClient.invalidateQueries({ queryKey: ['systemStatus'] });
    },
    onError: (error: any) => {
      toast.error(`Failed to stop: ${error.response?.data?.detail || error.message}`);
    }
  });

  const startOutreachMutation = useMutation({
    mutationFn: api.startOutreach,
    onSuccess: () => {
      toast.success("Outreach started");
      queryClient.invalidateQueries({ queryKey: ['systemStatus'] });
    },
    onError: (error: any) => {
      toast.error(`Failed to start outreach: ${error.response?.data?.detail || error.message}`);
    }
  });

  const pauseAgentMutation = useMutation({
    mutationFn: api.pauseAgent,
    onSuccess: () => {
      toast.success("Agent paused");
      queryClient.invalidateQueries({ queryKey: ['systemStatus'] });
    },
    onError: (error: any) => {
      toast.error(`Failed to pause: ${error.response?.data?.detail || error.message}`);
    }
  });

  const resumeAgentMutation = useMutation({
    mutationFn: api.resumeAgent,
    onSuccess: () => {
      toast.success("Agent resumed");
      queryClient.invalidateQueries({ queryKey: ['systemStatus'] });
    },
    onError: (error: any) => {
      toast.error(`Failed to resume: ${error.response?.data?.detail || error.message}`);
    }
  });

  const handleStartDiscovery = () => {
    if (!discoveryQuery.trim() || !discoveryLocation.trim()) {
      toast.error("Please fill in both search query and location");
      return;
    }
    startDiscoveryMutation.mutate({
      query: discoveryQuery.trim(),
      location: discoveryLocation.trim()
    });
  };

  if (statsLoading || logsLoading || leadsLoading) {
    return (
      <DashboardLayout>
        <div className="flex h-full items-center justify-center p-6">
          <div className="text-center">
            <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto mb-2" />
            <p className="text-muted-foreground">Loading dashboard data...</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  // Fallback if data is missing
  const stats = overview || {
    total_leads: 0,
    emails_sent_today: 0,
    replies_received: 0,
    pending_review: 0,
    rejected: 0
  };

  const recentLogs = logsData?.logs || [];
  const pendingLeadsList = Array.isArray(pendingLeads) ? pendingLeads.slice(0, 5) : [];
  const agentState = (systemStatus?.agent_state || 'IDLE').toUpperCase();
  const isHealthy = systemStatus?.is_healthy ?? true;

  return (
    <DashboardLayout>
      <div className="p-6">
        <div className="flex justify-between items-center mb-6">
          <PageHeader
            title="Dashboard Overview"
            description="Monitor your outreach agent activity"
          />
          <div className="flex gap-2">

            {agentState === 'IDLE' && (
              <>
                <Dialog open={discoveryDialogOpen} onOpenChange={setDiscoveryDialogOpen}>
                  <DialogTrigger asChild>
                    <Button>
                      <Search className="mr-2 h-4 w-4" /> Start Discovery
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="sm:max-w-[425px]">
                    <DialogHeader>
                      <DialogTitle>Start Lead Discovery</DialogTitle>
                      <DialogDescription>
                        Search Google Maps for businesses in a specific location.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                      <div className="grid gap-2">
                        <Label htmlFor="query">Business Type / Category</Label>
                        <Input
                          id="query"
                          placeholder="e.g., restaurants, plumbers, software companies"
                          value={discoveryQuery}
                          onChange={(e) => setDiscoveryQuery(e.target.value)}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="location">Location</Label>
                        <Input
                          id="location"
                          placeholder="e.g., Austin, TX or San Francisco, CA"
                          value={discoveryLocation}
                          onChange={(e) => setDiscoveryLocation(e.target.value)}
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button
                        variant="outline"
                        onClick={() => setDiscoveryDialogOpen(false)}
                      >
                        Cancel
                      </Button>
                      <Button
                        onClick={handleStartDiscovery}
                        disabled={startDiscoveryMutation.isPending || !discoveryQuery.trim() || !discoveryLocation.trim()}
                      >
                        {startDiscoveryMutation.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        ) : (
                          <Play className="h-4 w-4 mr-2" />
                        )}
                        Start Discovery
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>

                <Button
                  onClick={() => startOutreachMutation.mutate()}
                  variant="secondary"
                  disabled={startOutreachMutation.isPending || (stats.pending_review === 0 && pendingLeadsList.length === 0)}
                  title={stats.pending_review > 0 ? 'Start sending emails to approved leads' : 'No approved leads to send to'}
                >
                  {startOutreachMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <Mail className="mr-2 h-4 w-4" />
                  )}
                  Start Outreach
                </Button>
              </>
            )}

            {(agentState === 'DISCOVERING' || agentState === 'OUTREACH_RUNNING') && (
              <Button
                onClick={() => pauseAgentMutation.mutate()}
                variant="outline"
                disabled={pauseAgentMutation.isPending}
              >
                {pauseAgentMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Pause className="mr-2 h-4 w-4" />
                )}
                Pause
              </Button>
            )}

            {agentState === 'PAUSED' && (
              <Button
                onClick={() => resumeAgentMutation.mutate()}
                variant="default"
                disabled={resumeAgentMutation.isPending}
              >
                {resumeAgentMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Play className="mr-2 h-4 w-4" />
                )}
                Resume
              </Button>
            )}

            {(agentState === 'DISCOVERING' || agentState === 'OUTREACH_RUNNING' || agentState === 'PAUSED') && (
              <Button
                onClick={() => stopDiscoveryMutation.mutate()}
                variant="destructive"
                disabled={stopDiscoveryMutation.isPending}
              >
                {stopDiscoveryMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Square className="mr-2 h-4 w-4" />
                )}
                Stop
              </Button>
            )}

          </div>
        </div>

        {/* Status Banner */}
        <div className={`mb-6 p-4 rounded-lg border flex items-center justify-between ${!isHealthy ? 'bg-red-50 border-red-200' : 'bg-card border-border'
          }`}>
          <div className="flex items-center gap-3">
            {!isHealthy ? (
              <AlertCircle className="h-5 w-5 text-red-500" />
            ) : (
              <div className={`h-3 w-3 rounded-full ${agentState === 'IDLE' ? 'bg-gray-400' :
                agentState === 'PAUSED' ? 'bg-yellow-500' :
                  agentState === 'ERROR' ? 'bg-red-500' :
                    'bg-green-500 animate-pulse'
                }`} />
            )}
            <div>
              <h3 className="font-medium">
                Agent Status: {agentState}
                {!isHealthy && <span className="text-red-600 ml-2">(Unhealthy)</span>}
              </h3>
              <p className="text-sm text-muted-foreground">
                {systemStatus?.current_task ||
                  (agentState === 'IDLE' ? 'Ready for commands' :
                    systemStatus?.health_reason || 'Working...')}
              </p>
              {systemStatus?.discovery_query && systemStatus?.discovery_location && (
                <p className="text-sm text-muted-foreground">
                  Searching: "{systemStatus.discovery_query}" in {systemStatus.discovery_location}
                </p>
              )}
            </div>
          </div>
          <div className="text-sm text-muted-foreground">
            <span className="font-medium">{stats.emails_sent_today}</span> / {systemStatus?.email_quota || 20} emails today
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
          <StatCard
            title="Total Leads"
            value={stats.total_leads}
            icon={Users}
          />
          <StatCard
            title="Emails Sent Today"
            value={stats.emails_sent_today}
            icon={Mail}
          />
          <StatCard
            title="Replies Received"
            value={stats.replies_received}
            icon={MessageSquare}
          />
          <StatCard
            title="Pending Review"
            value={stats.pending_review}
            icon={UserCheck}
          />
          <StatCard
            title="Rejected"
            value={stats.rejected}
            icon={UserX}
          />
        </div>

        {/* Pending Leads for Review */}
        {pendingLeadsList.length > 0 && (
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-foreground">
                Pending Review ({stats.pending_review})
              </h2>
              <Link
                to="/leads"
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                View all →
              </Link>
            </div>
            <DataTable
              data={pendingLeadsList}
              columns={[
                {
                  header: 'Business',
                  accessor: (item: any) => (
                    <Link
                      to={`/leads/${item.lead_id}`}
                      className="font-medium hover:underline"
                    >
                      {item.business_name}
                    </Link>
                  ),
                },
                {
                  header: 'Email',
                  accessor: (item: any) => (
                    <span className={item.email ? '' : 'text-muted-foreground italic'}>
                      {item.email || 'No email'}
                    </span>
                  ),
                },
                {
                  header: 'Category',
                  accessor: 'category',
                },
                {
                  header: 'Tag',
                  accessor: (item: any) => (
                    <Badge variant="neutral">{item.tag || 'None'}</Badge>
                  ),
                },
                {
                  header: 'Location',
                  accessor: (item: any) => (
                    <span className="text-sm text-muted-foreground">
                      {item.location}
                    </span>
                  ),
                },
              ]}
            />
          </div>
        )}

        {/* Recent Activity */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-foreground">Recent Activity</h2>
            <Link
              to="/activity"
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              View all →
            </Link>
          </div>
          <DataTable
            data={recentLogs}
            columns={[
              {
                header: 'Time',
                accessor: (item: any) => (
                  <span className="font-mono text-xs text-muted-foreground">
                    {getRelativeTime(item.timestamp)}
                  </span>
                ),
                className: 'w-24',
              },
              {
                header: 'Module',
                accessor: (item: any) => (
                  <Badge variant={getModuleBadgeVariant(item.module)}>
                    {item.module}
                  </Badge>
                ),
                className: 'w-28',
              },
              {
                header: 'Action',
                accessor: (item: any) => (
                  <span>{item.action?.replace(/_/g, ' ')}</span>
                ),
              },
              {
                header: 'Status',
                accessor: (item: any) => (
                  <Badge variant={getStatusBadgeVariant(item.result)}>
                    {item.result}
                  </Badge>
                ),
                className: 'w-24',
              },
            ]}
          />
        </div>
      </div>
    </DashboardLayout>
  );
}
