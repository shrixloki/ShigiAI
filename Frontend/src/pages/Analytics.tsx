import { useState } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
    BarChart3,
    TrendingUp,
    TrendingDown,
    Users,
    Mail,
    MessageSquare,
    Target,
    CheckCircle2,
    XCircle,
    Clock,
    ArrowUpRight,
    ArrowDownRight
} from 'lucide-react';

export default function Analytics() {
    const { data: overview } = useQuery({
        queryKey: ['overview'],
        queryFn: api.getOverview,
        refetchInterval: 10000
    });

    const { data: systemStatus } = useQuery({
        queryKey: ['systemStatus'],
        queryFn: api.getSystemStatus,
        refetchInterval: 10000
    });

    // Calculate funnel metrics
    const totalLeads = overview?.total_leads || 0;
    const pendingReview = overview?.pending_review || 0;
    const approved = overview?.approved || 0;
    const rejected = overview?.rejected || 0;
    const emailsSent = overview?.emails_sent_today || 0;
    const repliesReceived = overview?.replies_received || 0;

    // Calculate conversion rates
    const approvalRate = totalLeads > 0 ? ((approved / totalLeads) * 100).toFixed(1) : 0;
    const replyRate = emailsSent > 0 ? ((repliesReceived / emailsSent) * 100).toFixed(1) : 0;

    return (
        <DashboardLayout>
            <div className="p-6 space-y-6">
                <PageHeader
                    title="Analytics & Insights"
                    description="Track your outreach performance and lead funnel metrics"
                />

                {/* Key Metrics Row */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <Card className="bg-gradient-to-br from-blue-500/10 to-blue-600/5 border-blue-500/20">
                        <CardHeader className="pb-2">
                            <CardDescription className="flex items-center gap-2">
                                <Users className="h-4 w-4" />
                                Total Leads
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold">{totalLeads}</div>
                            <p className="text-xs text-muted-foreground mt-1">
                                <span className="text-green-500 inline-flex items-center">
                                    <ArrowUpRight className="h-3 w-3" /> +12%
                                </span> from last week
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="bg-gradient-to-br from-green-500/10 to-green-600/5 border-green-500/20">
                        <CardHeader className="pb-2">
                            <CardDescription className="flex items-center gap-2">
                                <CheckCircle2 className="h-4 w-4" />
                                Approval Rate
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold">{approvalRate}%</div>
                            <p className="text-xs text-muted-foreground mt-1">
                                {approved} approved of {totalLeads} total
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="bg-gradient-to-br from-purple-500/10 to-purple-600/5 border-purple-500/20">
                        <CardHeader className="pb-2">
                            <CardDescription className="flex items-center gap-2">
                                <Mail className="h-4 w-4" />
                                Emails Sent
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold">{emailsSent}</div>
                            <p className="text-xs text-muted-foreground mt-1">
                                Today's outreach volume
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="bg-gradient-to-br from-orange-500/10 to-orange-600/5 border-orange-500/20">
                        <CardHeader className="pb-2">
                            <CardDescription className="flex items-center gap-2">
                                <MessageSquare className="h-4 w-4" />
                                Reply Rate
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold">{replyRate}%</div>
                            <p className="text-xs text-muted-foreground mt-1">
                                {repliesReceived} replies received
                            </p>
                        </CardContent>
                    </Card>
                </div>

                {/* Lead Funnel */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Target className="h-5 w-5" />
                            Lead Funnel
                        </CardTitle>
                        <CardDescription>
                            Track leads through your outreach pipeline
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            {/* Funnel stages */}
                            <div className="relative">
                                <div className="flex items-center gap-4">
                                    <div className="w-32 text-sm font-medium">Discovered</div>
                                    <div className="flex-1 h-8 bg-blue-500/20 rounded-lg relative overflow-hidden">
                                        <div
                                            className="h-full bg-blue-500 rounded-lg transition-all duration-500"
                                            style={{ width: '100%' }}
                                        />
                                        <span className="absolute inset-0 flex items-center justify-center text-sm font-medium text-white">
                                            {totalLeads} leads
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="relative">
                                <div className="flex items-center gap-4">
                                    <div className="w-32 text-sm font-medium">Pending Review</div>
                                    <div className="flex-1 h-8 bg-yellow-500/20 rounded-lg relative overflow-hidden">
                                        <div
                                            className="h-full bg-yellow-500 rounded-lg transition-all duration-500"
                                            style={{ width: totalLeads > 0 ? `${(pendingReview / totalLeads) * 100}%` : '0%' }}
                                        />
                                        <span className="absolute inset-0 flex items-center justify-center text-sm font-medium">
                                            {pendingReview} leads
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="relative">
                                <div className="flex items-center gap-4">
                                    <div className="w-32 text-sm font-medium">Approved</div>
                                    <div className="flex-1 h-8 bg-green-500/20 rounded-lg relative overflow-hidden">
                                        <div
                                            className="h-full bg-green-500 rounded-lg transition-all duration-500"
                                            style={{ width: totalLeads > 0 ? `${(approved / totalLeads) * 100}%` : '0%' }}
                                        />
                                        <span className="absolute inset-0 flex items-center justify-center text-sm font-medium">
                                            {approved} leads
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="relative">
                                <div className="flex items-center gap-4">
                                    <div className="w-32 text-sm font-medium">Contacted</div>
                                    <div className="flex-1 h-8 bg-purple-500/20 rounded-lg relative overflow-hidden">
                                        <div
                                            className="h-full bg-purple-500 rounded-lg transition-all duration-500"
                                            style={{ width: approved > 0 ? `${(emailsSent / approved) * 100}%` : '0%' }}
                                        />
                                        <span className="absolute inset-0 flex items-center justify-center text-sm font-medium">
                                            {emailsSent} leads
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="relative">
                                <div className="flex items-center gap-4">
                                    <div className="w-32 text-sm font-medium">Replied</div>
                                    <div className="flex-1 h-8 bg-emerald-500/20 rounded-lg relative overflow-hidden">
                                        <div
                                            className="h-full bg-emerald-500 rounded-lg transition-all duration-500"
                                            style={{ width: emailsSent > 0 ? `${(repliesReceived / emailsSent) * 100}%` : '0%' }}
                                        />
                                        <span className="absolute inset-0 flex items-center justify-center text-sm font-medium">
                                            {repliesReceived} leads
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Campaign Performance & Template Stats */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Campaign Performance</CardTitle>
                            <CardDescription>Email campaign metrics over time</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-4">
                                <div className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 bg-blue-500/20 rounded-lg">
                                            <Mail className="h-4 w-4 text-blue-500" />
                                        </div>
                                        <div>
                                            <div className="font-medium">Initial Outreach</div>
                                            <div className="text-xs text-muted-foreground">First contact emails</div>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <div className="font-bold">{overview?.sent_initial || 0}</div>
                                        <div className="text-xs text-muted-foreground">sent</div>
                                    </div>
                                </div>

                                <div className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 bg-yellow-500/20 rounded-lg">
                                            <Mail className="h-4 w-4 text-yellow-500" />
                                        </div>
                                        <div>
                                            <div className="font-medium">Follow-up Emails</div>
                                            <div className="text-xs text-muted-foreground">Second & third touch</div>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <div className="font-bold">{overview?.sent_followup || 0}</div>
                                        <div className="text-xs text-muted-foreground">sent</div>
                                    </div>
                                </div>

                                <div className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 bg-green-500/20 rounded-lg">
                                            <MessageSquare className="h-4 w-4 text-green-500" />
                                        </div>
                                        <div>
                                            <div className="font-medium">Replies Received</div>
                                            <div className="text-xs text-muted-foreground">Response rate tracking</div>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <div className="font-bold">{repliesReceived}</div>
                                        <div className="text-xs text-green-500">{replyRate}% rate</div>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Lead Status Distribution</CardTitle>
                            <CardDescription>Current state of your lead pipeline</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-4">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <div className="w-3 h-3 rounded-full bg-yellow-500" />
                                        <span className="text-sm">Pending Review</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="font-bold">{pendingReview}</span>
                                        <Badge variant="warning">{totalLeads > 0 ? ((pendingReview / totalLeads) * 100).toFixed(0) : 0}%</Badge>
                                    </div>
                                </div>

                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <div className="w-3 h-3 rounded-full bg-green-500" />
                                        <span className="text-sm">Approved</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="font-bold">{approved}</span>
                                        <Badge variant="success">{totalLeads > 0 ? ((approved / totalLeads) * 100).toFixed(0) : 0}%</Badge>
                                    </div>
                                </div>

                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <div className="w-3 h-3 rounded-full bg-red-500" />
                                        <span className="text-sm">Rejected</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="font-bold">{rejected}</span>
                                        <Badge variant="error">{totalLeads > 0 ? ((rejected / totalLeads) * 100).toFixed(0) : 0}%</Badge>
                                    </div>
                                </div>

                                <div className="pt-4 border-t">
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="text-muted-foreground">Email Quota Today</span>
                                        <span className="font-medium">
                                            {emailsSent} / {systemStatus?.email_quota || 20}
                                        </span>
                                    </div>
                                    <div className="mt-2 h-2 bg-secondary rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-primary rounded-full transition-all"
                                            style={{ width: `${(emailsSent / (systemStatus?.email_quota || 20)) * 100}%` }}
                                        />
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </DashboardLayout>
    );
}
