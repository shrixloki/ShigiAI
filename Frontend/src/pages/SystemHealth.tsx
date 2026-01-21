import { CheckCircle, AlertTriangle, XCircle, Clock, Mail, AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { getRelativeTime, formatDateTime } from '@/lib/utils';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from 'sonner';

const getStatusIcon = (isHealthy: boolean, agentState: string) => {
  if (!isHealthy || agentState === 'ERROR') return XCircle;
  if (agentState === 'PAUSED' || agentState === 'STOPPING') return AlertTriangle;
  return CheckCircle;
};

const getStatusBadgeVariant = (isHealthy: boolean, agentState: string) => {
  if (!isHealthy || agentState === 'ERROR') return 'error';
  if (agentState === 'PAUSED' || agentState === 'STOPPING') return 'warning';
  return 'success';
};

const getAgentStateBadgeVariant = (state: string) => {
  switch (state) {
    case 'IDLE':
      return 'neutral';
    case 'DISCOVERING':
    case 'OUTREACH_RUNNING':
      return 'success';
    case 'PAUSED':
      return 'warning';
    case 'STOPPING':
      return 'warning';
    case 'ERROR':
      return 'error';
    default:
      return 'neutral';
  }
};

export default function SystemHealth() {
  const queryClient = useQueryClient();

  const { data: systemStatus, isLoading, refetch } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: api.getSystemStatus,
    refetchInterval: 3000
  });

  const { data: logsData } = useQuery({
    queryKey: ['errorLogs'],
    queryFn: () => api.getLogs({ limit: 50 }),
    refetchInterval: 10000
  });

  const resetAgentMutation = useMutation({
    mutationFn: api.resetAgent,
    onSuccess: () => {
      toast.success('Agent reset successfully');
      queryClient.invalidateQueries({ queryKey: ['systemStatus'] });
    },
    onError: (error: any) => {
      toast.error(`Failed to reset: ${error.response?.data?.detail || error.message}`);
    }
  });

  if (isLoading || !systemStatus) {
    return (
      <DashboardLayout>
        <div className="p-6">
          <PageHeader title="System Health" description="Monitor agent status and resource usage" />
          <div className="space-y-4 mt-6">
            <Skeleton className="h-24 w-full" />
            <div className="grid grid-cols-3 gap-4">
              <Skeleton className="h-20" />
              <Skeleton className="h-20" />
              <Skeleton className="h-20" />
            </div>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  const isHealthy = systemStatus.is_healthy;
  const agentState = (systemStatus.agent_state || 'IDLE').toUpperCase();
  const StatusIcon = getStatusIcon(isHealthy, agentState);
  const quotaPercentage = systemStatus.email_quota > 0
    ? (systemStatus.emails_sent_today / systemStatus.email_quota) * 100
    : 0;

  // Filter error logs from recent logs
  const errorLogs = (logsData?.logs || [])
    .filter((log: any) => log.result === 'error')
    .slice(0, 10);

  return (
    <DashboardLayout>
      <div className="p-6">
        <div className="flex justify-between items-start mb-6">
          <PageHeader
            title="System Health"
            description="Monitor agent status and resource usage"
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>

        {/* Status Card */}
        <div className="bg-card border border-border rounded-lg p-6 mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`p-3 rounded-full ${isHealthy && agentState !== 'ERROR' ? 'bg-status-success-bg' :
                agentState === 'PAUSED' ? 'bg-status-warning-bg' : 'bg-status-error-bg'
                }`}>
                <StatusIcon className={`h-6 w-6 ${isHealthy && agentState !== 'ERROR' ? 'text-status-success' :
                  agentState === 'PAUSED' ? 'text-status-warning' : 'text-status-error'
                  }`} />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-foreground">
                  System Status
                </h2>
                <p className="text-sm text-muted-foreground">
                  {systemStatus.health_reason || (isHealthy ? 'All systems operational' : 'Issues detected')}
                </p>
                {systemStatus.error_message && (
                  <p className="text-sm text-red-500 mt-1">
                    Error: {systemStatus.error_message}
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={getAgentStateBadgeVariant(agentState)} className="text-sm px-3 py-1">
                {agentState}
              </Badge>
              {agentState === 'ERROR' && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => resetAgentMutation.mutate()}
                  disabled={resetAgentMutation.isPending}
                >
                  {resetAgentMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-1" />
                  ) : null}
                  Reset Agent
                </Button>
              )}
            </div>
          </div>

          {/* Current Task Info */}
          {(systemStatus.current_task || systemStatus.discovery_query) && (
            <div className="mt-4 pt-4 border-t border-border">
              {systemStatus.current_task && (
                <p className="text-sm">
                  <span className="text-muted-foreground">Current Task:</span>{' '}
                  <span className="font-medium">{systemStatus.current_task}</span>
                </p>
              )}
              {systemStatus.discovery_query && systemStatus.discovery_location && (
                <p className="text-sm mt-1">
                  <span className="text-muted-foreground">Discovery:</span>{' '}
                  <span className="font-medium">"{systemStatus.discovery_query}" in {systemStatus.discovery_location}</span>
                </p>
              )}
            </div>
          )}
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-card border border-border rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-secondary rounded">
                <Clock className="h-4 w-4 text-muted-foreground" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Last Heartbeat
                </p>
                <p className="text-sm font-mono mt-1">
                  {systemStatus.last_heartbeat ? getRelativeTime(systemStatus.last_heartbeat) : 'N/A'}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-card border border-border rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-secondary rounded">
                <Mail className="h-4 w-4 text-muted-foreground" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Emails Today
                </p>
                <p className="text-sm font-semibold mt-1">
                  {systemStatus.emails_sent_today} / {systemStatus.email_quota}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-card border border-border rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-secondary rounded">
                <AlertCircle className="h-4 w-4 text-muted-foreground" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Errors (24h)
                </p>
                <p className="text-sm font-semibold mt-1">
                  {systemStatus.error_count_24h}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-card border border-border rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-secondary rounded">
                <CheckCircle className="h-4 w-4 text-muted-foreground" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Total Leads
                </p>
                <p className="text-sm font-semibold mt-1">
                  {systemStatus.lead_counts?.total || 0}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Email Quota */}
        <div className="bg-card border border-border rounded-lg p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-foreground">Email Quota Usage</h3>
            <span className="text-sm text-muted-foreground">
              {systemStatus.emails_sent_today} / {systemStatus.email_quota} sent
            </span>
          </div>
          <Progress value={quotaPercentage} className="h-2" />
          <p className="text-xs text-muted-foreground mt-2">
            {Math.max(0, 100 - quotaPercentage).toFixed(0)}% remaining today
          </p>
        </div>

        {/* Lead Counts */}
        <div className="bg-card border border-border rounded-lg p-6 mb-6">
          <h3 className="text-sm font-semibold text-foreground mb-4">Lead Statistics</h3>
          <div className="grid grid-cols-5 gap-4">
            <div className="text-center">
              <p className="text-2xl font-bold">{systemStatus.lead_counts?.total || 0}</p>
              <p className="text-xs text-muted-foreground">Total</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-yellow-500">{systemStatus.lead_counts?.pending_review || 0}</p>
              <p className="text-xs text-muted-foreground">Pending</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-green-500">{systemStatus.lead_counts?.approved || 0}</p>
              <p className="text-xs text-muted-foreground">Approved</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-red-500">{systemStatus.lead_counts?.rejected || 0}</p>
              <p className="text-xs text-muted-foreground">Rejected</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-blue-500">{systemStatus.lead_counts?.replied || 0}</p>
              <p className="text-xs text-muted-foreground">Replied</p>
            </div>
          </div>
        </div>

        {/* Errors Log */}
        <div>
          <h3 className="text-sm font-semibold text-foreground mb-4">Recent Errors</h3>

          {errorLogs.length === 0 ? (
            <div className="bg-card border border-border rounded-lg p-8 text-center">
              <CheckCircle className="h-8 w-8 text-status-success mx-auto mb-2" />
              <p className="text-muted-foreground">No recent errors</p>
            </div>
          ) : (
            <div className="bg-card border border-border rounded-lg overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border bg-secondary/50">
                    <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">
                      Timestamp
                    </th>
                    <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">
                      Module
                    </th>
                    <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">
                      Action
                    </th>
                    <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">
                      Details
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {errorLogs.map((error: any, index: number) => (
                    <tr key={error.id || index} className="border-b border-border last:border-0">
                      <td className="px-4 py-3">
                        <span className="font-mono text-xs text-muted-foreground">
                          {formatDateTime(error.timestamp)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="neutral">{error.module}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm">{error.action?.replace(/_/g, ' ')}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm text-muted-foreground">
                          {typeof error.details === 'string'
                            ? error.details
                            : error.details
                              ? JSON.stringify(error.details)
                              : '—'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
