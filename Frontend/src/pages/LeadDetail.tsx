import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft,
  Mail,
  MessageSquare,
  Activity,
  RefreshCw,
  Check,
  X,
  Loader2,
  Globe,
  Building2,
  Users,
  Briefcase,
  TrendingUp,
  Target,
  StickyNote,
  Plus,
  Send,
  Phone,
  Linkedin,
  Twitter,
  Github,
  ExternalLink,
  Clock,
  Star,
  Zap
} from 'lucide-react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
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
    case 'approved': return 'success';
    case 'rejected': return 'error';
    case 'pending': return 'warning';
    default: return 'neutral';
  }
};

const getOutreachStatusBadgeVariant = (status: string) => {
  switch (status) {
    case 'sent_initial':
    case 'sent_followup':
    case 'replied':
      return 'success';
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
    case 'send_initial': return 'Initial Email Sent';
    case 'send_followup': return 'Follow-up Sent';
    case 'detect_reply': return 'Reply Detected';
    case 'approve': return 'Lead Approved';
    case 'reject': return 'Lead Rejected';
    case 'discover_one': return 'Lead Discovered';
    case 'analyze': return 'Website Analyzed';
    default: return action.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  }
};

const getResultBadgeVariant = (result: string) => {
  switch (result) {
    case 'success': return 'success';
    case 'error': return 'error';
    case 'blocked':
    case 'skipped': return 'warning';
    default: return 'neutral';
  }
};

export default function LeadDetail() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [noteDialogOpen, setNoteDialogOpen] = useState(false);
  const [newNote, setNewNote] = useState('');
  const [notes, setNotes] = useState<string[]>([
    'Initial contact made via cold outreach',
    'Expressed interest in web development services'
  ]);

  const { data, isLoading, error } = useQuery({
    queryKey: ['leadDetail', id],
    queryFn: () => fetchLeadDetail(id!),
    enabled: !!id,
    refetchInterval: 10000
  });

  const approveMutation = useMutation({
    mutationFn: () => approveLead(id!),
    onSuccess: () => {
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
    onSuccess: () => {
      toast.success('Lead rejected successfully');
      queryClient.invalidateQueries({ queryKey: ['leadDetail', id] });
      queryClient.invalidateQueries({ queryKey: ['leads'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
    },
    onError: (error: any) => {
      toast.error(`Failed to reject lead: ${error.response?.data?.detail || error.message}`);
    }
  });

  const handleAddNote = () => {
    if (!newNote.trim()) return;
    setNotes([...notes, newNote]);
    setNewNote('');
    setNoteDialogOpen(false);
    toast.success('Note added');
  };

  // Mock enrichment data (will be replaced with real API data)
  const enrichmentData = {
    techStack: ['React', 'Node.js', 'PostgreSQL', 'AWS'],
    companySize: '10-50 employees',
    stage: 'Growth Stage',
    hiringSignals: true,
    linkedin: 'https://linkedin.com/company/example',
    twitter: 'https://twitter.com/example',
    contactIntent: 'High',
    decisionMaker: 'John Smith - CEO',
    confidence: 85
  };

  // Mock score breakdown
  const scoreBreakdown = {
    intent: 85,
    relevance: 78,
    recency: 92,
    industryFit: 70,
    outreachReadiness: 88
  };

  const compositeScore = Math.round(
    (scoreBreakdown.intent + scoreBreakdown.relevance + scoreBreakdown.recency +
      scoreBreakdown.industryFit + scoreBreakdown.outreachReadiness) / 5
  );

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

        {/* Lead Header with Score */}
        <div className="grid grid-cols-4 gap-6 mb-6">
          <div className="col-span-3">
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-xl flex items-center gap-2">
                      <Building2 className="h-5 w-5" />
                      {lead.business_name}
                    </CardTitle>
                    <CardDescription className="mt-1">
                      {lead.email || 'No email found'} • {lead.location || 'Unknown location'}
                    </CardDescription>
                    {lead.website_url && (
                      <a
                        href={lead.website_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-primary hover:underline mt-1 inline-flex items-center gap-1"
                      >
                        <Globe className="h-3 w-3" />
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
              </CardHeader>
              <CardContent>
                {/* Action Buttons */}
                {lead.review_status === 'pending' && (
                  <div className="flex gap-2 mb-4 pb-4 border-b">
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
                    <Button variant="outline">
                      <Send className="h-4 w-4 mr-2" />
                      Send Test Email
                    </Button>
                  </div>
                )}

                {/* Quick Info Grid */}
                <div className="grid grid-cols-4 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground uppercase">Category</p>
                    <p className="text-sm font-medium mt-1">{lead.category || 'Unknown'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase">Company Size</p>
                    <p className="text-sm font-medium mt-1">{enrichmentData.companySize}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase">Stage</p>
                    <p className="text-sm font-medium mt-1">{enrichmentData.stage}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase">Decision Maker</p>
                    <p className="text-sm font-medium mt-1">{enrichmentData.decisionMaker}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Score Card */}
          <div>
            <Card className="bg-gradient-to-br from-primary/10 to-primary/5 border-primary/20">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Star className="h-4 w-4 text-yellow-500" />
                  Lead Score
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-center mb-4">
                  <div className="text-5xl font-bold text-primary">{compositeScore}</div>
                  <p className="text-xs text-muted-foreground mt-1">out of 100</p>
                </div>
                <div className="space-y-2">
                  {Object.entries(scoreBreakdown).map(([key, value]) => (
                    <div key={key} className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground capitalize w-24">
                        {key.replace(/([A-Z])/g, ' $1').trim()}
                      </span>
                      <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${value >= 80 ? 'bg-green-500' : value >= 60 ? 'bg-yellow-500' : 'bg-red-500'
                            }`}
                          style={{ width: `${value}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium w-8 text-right">{value}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Tabs for Details */}
        <Tabs defaultValue="enrichment" className="space-y-4">
          <TabsList>
            <TabsTrigger value="enrichment" className="flex items-center gap-2">
              <Zap className="h-4 w-4" />
              Enrichment
            </TabsTrigger>
            <TabsTrigger value="activity" className="flex items-center gap-2">
              <Activity className="h-4 w-4" />
              Activity
            </TabsTrigger>
            <TabsTrigger value="notes" className="flex items-center gap-2">
              <StickyNote className="h-4 w-4" />
              Notes ({notes.length})
            </TabsTrigger>
            <TabsTrigger value="emails" className="flex items-center gap-2">
              <Mail className="h-4 w-4" />
              Emails
            </TabsTrigger>
          </TabsList>

          {/* Enrichment Tab */}
          <TabsContent value="enrichment">
            <div className="grid grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Tech Stack</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {enrichmentData.techStack.map((tech) => (
                      <Badge key={tech} variant="neutral">{tech}</Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Signals</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm">Hiring Signals</span>
                    <Badge variant={enrichmentData.hiringSignals ? 'success' : 'neutral'}>
                      {enrichmentData.hiringSignals ? 'Active' : 'None'}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm">Contact Intent</span>
                    <Badge variant="success">{enrichmentData.contactIntent}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm">Confidence</span>
                    <span className="font-medium">{enrichmentData.confidence}%</span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Social Profiles</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <a
                    href={enrichmentData.linkedin}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm text-primary hover:underline"
                  >
                    <Linkedin className="h-4 w-4" />
                    LinkedIn Profile
                    <ExternalLink className="h-3 w-3" />
                  </a>
                  <a
                    href={enrichmentData.twitter}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm text-primary hover:underline"
                  >
                    <Twitter className="h-4 w-4" />
                    Twitter/X Profile
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Business Details</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Company Size</span>
                    <span>{enrichmentData.companySize}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Business Stage</span>
                    <span>{enrichmentData.stage}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Category</span>
                    <span>{lead.category || 'Unknown'}</span>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Activity Tab */}
          <TabsContent value="activity">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Activity Timeline</CardTitle>
              </CardHeader>
              <CardContent>
                {!action_history || action_history.length === 0 ? (
                  <p className="text-muted-foreground text-center py-8">No activity history available</p>
                ) : (
                  <div className="space-y-4">
                    {action_history.map((item: any) => {
                      const Icon = getHistoryIcon(item.action);
                      return (
                        <div key={item.id} className="flex items-start gap-3 p-3 bg-secondary/50 rounded-lg">
                          <div className="p-2 bg-background rounded">
                            <Icon className="h-4 w-4 text-muted-foreground" />
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium">
                                  {getHistoryTypeLabel(item.action)}
                                </span>
                                <Badge variant={getResultBadgeVariant(item.result)} className="text-xs">
                                  {item.result}
                                </Badge>
                              </div>
                              <span className="text-xs text-muted-foreground">
                                {item.timestamp ? getRelativeTime(item.timestamp) : ''}
                              </span>
                            </div>
                            {item.details && (
                              <p className="mt-1 text-sm text-muted-foreground">{item.details}</p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Notes Tab */}
          <TabsContent value="notes">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm">Internal Notes</CardTitle>
                  <Dialog open={noteDialogOpen} onOpenChange={setNoteDialogOpen}>
                    <DialogTrigger asChild>
                      <Button size="sm">
                        <Plus className="h-4 w-4 mr-1" />
                        Add Note
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Add Note</DialogTitle>
                        <DialogDescription>
                          Add an internal note about this lead
                        </DialogDescription>
                      </DialogHeader>
                      <Textarea
                        placeholder="Enter your note..."
                        value={newNote}
                        onChange={(e) => setNewNote(e.target.value)}
                        className="min-h-[100px]"
                      />
                      <DialogFooter>
                        <Button variant="outline" onClick={() => setNoteDialogOpen(false)}>
                          Cancel
                        </Button>
                        <Button onClick={handleAddNote}>Save Note</Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </div>
              </CardHeader>
              <CardContent>
                {notes.length === 0 ? (
                  <p className="text-muted-foreground text-center py-8">No notes yet</p>
                ) : (
                  <div className="space-y-3">
                    {notes.map((note, index) => (
                      <div key={index} className="p-3 bg-secondary/50 rounded-lg">
                        <p className="text-sm">{note}</p>
                        <p className="text-xs text-muted-foreground mt-2">
                          Added {new Date().toLocaleDateString()}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Emails Tab */}
          <TabsContent value="emails">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Email History</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8 text-muted-foreground">
                  <Mail className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No emails sent to this lead yet</p>
                  {lead.review_status === 'approved' && (
                    <Button className="mt-4" variant="outline">
                      <Send className="h-4 w-4 mr-2" />
                      Send First Email
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}
