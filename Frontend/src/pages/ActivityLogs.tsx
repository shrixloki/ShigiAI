import { useState, useMemo } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { DataTable } from '@/components/dashboard/DataTable';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Loader2 } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { formatDateTime } from '@/lib/utils';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

interface ActivityLog {
  id: number;
  timestamp: string;
  lead_id: string;
  module: string;
  action: string;
  result: string;
  details: string;
}

const modules = ['All', 'hunter', 'website_analyzer', 'messenger', 'followup', 'review', 'reply_detector'] as const;
const dateFilters = ['All Time', 'Today', 'Last 7 Days', 'Last 30 Days'] as const;

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
    case 'reply_detector':
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
    case 'info':
      return 'neutral';
    default:
      return 'neutral';
  }
};

export default function ActivityLogs() {
  const [moduleFilter, setModuleFilter] = useState<string>('All');
  const [dateFilter, setDateFilter] = useState<string>('All Time');

  const { data: logsData, isLoading } = useQuery({
    queryKey: ['logs', moduleFilter],
    queryFn: () => api.getLogs({
      module: moduleFilter !== 'All' ? moduleFilter : undefined,
      limit: 200
    }),
    refetchInterval: 5000
  });

  const logs = logsData?.logs || [];

  const filteredLogs = useMemo(() => {
    let filtered = [...logs];

    if (dateFilter !== 'All Time') {
      const now = new Date();
      const cutoff = new Date();

      switch (dateFilter) {
        case 'Today':
          cutoff.setHours(0, 0, 0, 0);
          break;
        case 'Last 7 Days':
          cutoff.setDate(now.getDate() - 7);
          break;
        case 'Last 30 Days':
          cutoff.setDate(now.getDate() - 30);
          break;
      }

      filtered = filtered.filter((log) => new Date(log.timestamp) >= cutoff);
    }

    return filtered;
  }, [logs, dateFilter]);

  const resetFilters = () => {
    setModuleFilter('All');
    setDateFilter('All Time');
  };

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="p-6">
          <PageHeader title="Activity Logs" description="View all agent activity and actions" />
          <div className="space-y-4 mt-6">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-60 w-full" />
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-6">
        <PageHeader
          title="Activity Logs"
          description="View all agent activity and actions"
        />

        {/* Filters */}
        <div className="flex items-center gap-3 mb-6">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Module:</span>
            <Select value={moduleFilter} onValueChange={setModuleFilter}>
              <SelectTrigger className="w-36 h-8 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {modules.map((module) => (
                  <SelectItem key={module} value={module}>
                    {module === 'All' ? 'All' : module.replace(/_/g, ' ')}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Date:</span>
            <Select value={dateFilter} onValueChange={setDateFilter}>
              <SelectTrigger className="w-32 h-8 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {dateFilters.map((filter) => (
                  <SelectItem key={filter} value={filter}>
                    {filter}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {(moduleFilter !== 'All' || dateFilter !== 'All Time') && (
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
            {filteredLogs.length} entries
          </span>
        </div>

        {/* Table */}
        <DataTable
          data={filteredLogs}
          columns={[
            {
              header: 'Timestamp',
              accessor: (item: ActivityLog) => (
                <span className="font-mono text-xs text-muted-foreground">
                  {formatDateTime(item.timestamp)}
                </span>
              ),
              className: 'w-36',
            },
            {
              header: 'Lead ID',
              accessor: (item: ActivityLog) => (
                <span className="font-mono text-xs">
                  {item.lead_id || '—'}
                </span>
              ),
              className: 'w-24',
            },
            {
              header: 'Module',
              accessor: (item: ActivityLog) => (
                <Badge variant={getModuleBadgeVariant(item.module)}>
                  {item.module}
                </Badge>
              ),
              className: 'w-32',
            },
            {
              header: 'Action',
              accessor: (item: ActivityLog) => (
                <span>{item.action?.replace(/_/g, ' ')}</span>
              ),
            },
            {
              header: 'Result',
              accessor: (item: ActivityLog) => (
                <Badge variant={getStatusBadgeVariant(item.result)}>
                  {item.result}
                </Badge>
              ),
              className: 'w-24',
            },
            {
              header: 'Details',
              accessor: (item: ActivityLog) => (
                <span className="text-sm text-muted-foreground truncate max-w-xs block">
                  {typeof item.details === 'string'
                    ? item.details
                    : item.details
                      ? JSON.stringify(item.details)
                      : '—'}
                </span>
              ),
            },
          ]}
          emptyMessage="No activity logs match your filters"
        />
      </div>
    </DashboardLayout>
  );
}
