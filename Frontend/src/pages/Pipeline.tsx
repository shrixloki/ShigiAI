import { useState } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import {
    Plus,
    Mail,
    MessageSquare,
    Phone,
    Calendar,
    DollarSign,
    Building2,
    User,
    StickyNote,
    Clock,
    ArrowRight,
    MoreHorizontal,
    ExternalLink
} from 'lucide-react';
import { Link } from 'react-router-dom';

interface Opportunity {
    id: string;
    leadId: string;
    businessName: string;
    contactName: string;
    email: string;
    stage: 'replied' | 'meeting_scheduled' | 'proposal_sent' | 'negotiating' | 'closed_won' | 'closed_lost';
    value: number;
    probability: number;
    lastActivity: string;
    notes: string[];
}

// Pipeline stages
const stages = [
    { id: 'replied', name: 'Replied', color: 'bg-blue-500' },
    { id: 'meeting_scheduled', name: 'Meeting Scheduled', color: 'bg-yellow-500' },
    { id: 'proposal_sent', name: 'Proposal Sent', color: 'bg-purple-500' },
    { id: 'negotiating', name: 'Negotiating', color: 'bg-orange-500' },
    { id: 'closed_won', name: 'Closed Won', color: 'bg-green-500' },
    { id: 'closed_lost', name: 'Closed Lost', color: 'bg-red-500' },
];

// Sample opportunities
const sampleOpportunities: Opportunity[] = [
    {
        id: '1',
        leadId: 'lead-1',
        businessName: 'TechStart Inc',
        contactName: 'John Smith',
        email: 'john@techstart.com',
        stage: 'replied',
        value: 5000,
        probability: 20,
        lastActivity: new Date().toISOString(),
        notes: ['Interested in web development services', 'Asked for portfolio']
    },
    {
        id: '2',
        leadId: 'lead-2',
        businessName: 'Digital Solutions LLC',
        contactName: 'Sarah Johnson',
        email: 'sarah@digitalsol.com',
        stage: 'meeting_scheduled',
        value: 10000,
        probability: 50,
        lastActivity: new Date(Date.now() - 86400000).toISOString(),
        notes: ['Meeting scheduled for next week', 'Looking for long-term partnership']
    },
    {
        id: '3',
        leadId: 'lead-3',
        businessName: 'Growth Labs',
        contactName: 'Mike Brown',
        email: 'mike@growthlabs.io',
        stage: 'proposal_sent',
        value: 15000,
        probability: 60,
        lastActivity: new Date(Date.now() - 172800000).toISOString(),
        notes: ['Sent proposal on Monday', 'Waiting for feedback']
    }
];

export default function Pipeline() {
    const [opportunities, setOpportunities] = useState<Opportunity[]>(sampleOpportunities);
    const [selectedOpportunity, setSelectedOpportunity] = useState<Opportunity | null>(null);
    const [noteDialogOpen, setNoteDialogOpen] = useState(false);
    const [newNote, setNewNote] = useState('');

    const { data: leads } = useQuery({
        queryKey: ['allLeads'],
        queryFn: () => api.getLeads({}),
        refetchInterval: 30000
    });

    const getOpportunitiesByStage = (stageId: string) => {
        return opportunities.filter(o => o.stage === stageId);
    };

    const getTotalValue = (stageId: string) => {
        return getOpportunitiesByStage(stageId).reduce((sum, o) => sum + o.value, 0);
    };

    const getWeightedValue = (stageId: string) => {
        return getOpportunitiesByStage(stageId).reduce((sum, o) => sum + (o.value * o.probability / 100), 0);
    };

    const handleMoveStage = (opportunityId: string, newStage: Opportunity['stage']) => {
        setOpportunities(opportunities.map(o => {
            if (o.id === opportunityId) {
                toast.success(`Moved to ${stages.find(s => s.id === newStage)?.name}`);
                return { ...o, stage: newStage };
            }
            return o;
        }));
    };

    const handleAddNote = () => {
        if (!selectedOpportunity || !newNote.trim()) return;

        setOpportunities(opportunities.map(o => {
            if (o.id === selectedOpportunity.id) {
                return { ...o, notes: [...o.notes, newNote] };
            }
            return o;
        }));

        setNewNote('');
        setNoteDialogOpen(false);
        toast.success('Note added');
    };

    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 0
        }).format(value);
    };

    const getTimeAgo = (date: string) => {
        const diff = Date.now() - new Date(date).getTime();
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        if (days === 0) return 'Today';
        if (days === 1) return 'Yesterday';
        return `${days} days ago`;
    };

    return (
        <DashboardLayout>
            <div className="p-6 space-y-6">
                <PageHeader
                    title="CRM Pipeline"
                    description="Track opportunities through your sales pipeline"
                />

                {/* Pipeline Summary */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card>
                        <CardContent className="pt-4">
                            <div className="text-2xl font-bold">{opportunities.length}</div>
                            <div className="text-sm text-muted-foreground">Total Opportunities</div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-4">
                            <div className="text-2xl font-bold text-green-500">
                                {formatCurrency(opportunities.reduce((sum, o) => sum + o.value, 0))}
                            </div>
                            <div className="text-sm text-muted-foreground">Total Pipeline Value</div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-4">
                            <div className="text-2xl font-bold text-blue-500">
                                {formatCurrency(opportunities.reduce((sum, o) => sum + (o.value * o.probability / 100), 0))}
                            </div>
                            <div className="text-sm text-muted-foreground">Weighted Value</div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-4">
                            <div className="text-2xl font-bold">
                                {opportunities.filter(o => o.stage === 'closed_won').length}
                            </div>
                            <div className="text-sm text-muted-foreground">Closed Won</div>
                        </CardContent>
                    </Card>
                </div>

                {/* Pipeline Kanban */}
                <div className="overflow-x-auto">
                    <div className="flex gap-4 min-w-max pb-4">
                        {stages.slice(0, 4).map((stage) => (
                            <div key={stage.id} className="w-80 flex-shrink-0">
                                <Card className="h-full">
                                    <CardHeader className="pb-3">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <div className={`w-3 h-3 rounded-full ${stage.color}`} />
                                                <CardTitle className="text-sm font-medium">{stage.name}</CardTitle>
                                            </div>
                                            <Badge variant="neutral">{getOpportunitiesByStage(stage.id).length}</Badge>
                                        </div>
                                        <CardDescription className="text-xs">
                                            {formatCurrency(getTotalValue(stage.id))} total
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent className="space-y-3">
                                        {getOpportunitiesByStage(stage.id).map((opportunity) => (
                                            <div
                                                key={opportunity.id}
                                                className="p-3 bg-secondary/50 rounded-lg border border-border hover:border-primary/50 transition-colors cursor-pointer"
                                                onClick={() => setSelectedOpportunity(opportunity)}
                                            >
                                                <div className="flex items-start justify-between mb-2">
                                                    <div className="flex items-center gap-2">
                                                        <Avatar className="h-8 w-8">
                                                            <AvatarFallback className="bg-primary/20 text-primary text-xs">
                                                                {opportunity.businessName.substring(0, 2).toUpperCase()}
                                                            </AvatarFallback>
                                                        </Avatar>
                                                        <div>
                                                            <div className="font-medium text-sm">{opportunity.businessName}</div>
                                                            <div className="text-xs text-muted-foreground">{opportunity.contactName}</div>
                                                        </div>
                                                    </div>
                                                    <Button variant="ghost" size="icon" className="h-6 w-6">
                                                        <MoreHorizontal className="h-4 w-4" />
                                                    </Button>
                                                </div>

                                                <div className="flex items-center justify-between text-xs">
                                                    <span className="text-green-500 font-medium">{formatCurrency(opportunity.value)}</span>
                                                    <span className="text-muted-foreground">{opportunity.probability}% likely</span>
                                                </div>

                                                <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                                                    <Clock className="h-3 w-3" />
                                                    {getTimeAgo(opportunity.lastActivity)}
                                                </div>

                                                {/* Quick actions */}
                                                <div className="flex items-center gap-1 mt-2 pt-2 border-t border-border/50">
                                                    <Button variant="ghost" size="icon" className="h-6 w-6">
                                                        <Mail className="h-3 w-3" />
                                                    </Button>
                                                    <Button variant="ghost" size="icon" className="h-6 w-6">
                                                        <Phone className="h-3 w-3" />
                                                    </Button>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-6 w-6"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            setSelectedOpportunity(opportunity);
                                                            setNoteDialogOpen(true);
                                                        }}
                                                    >
                                                        <StickyNote className="h-3 w-3" />
                                                    </Button>
                                                    <div className="flex-1" />
                                                    <Link to={`/leads/${opportunity.leadId}`}>
                                                        <Button variant="ghost" size="icon" className="h-6 w-6">
                                                            <ExternalLink className="h-3 w-3" />
                                                        </Button>
                                                    </Link>
                                                </div>
                                            </div>
                                        ))}

                                        {getOpportunitiesByStage(stage.id).length === 0 && (
                                            <div className="text-center py-8 text-muted-foreground text-sm">
                                                No opportunities
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Opportunity Detail Modal */}
                <Dialog open={!!selectedOpportunity && !noteDialogOpen} onOpenChange={(open) => !open && setSelectedOpportunity(null)}>
                    <DialogContent className="max-w-2xl">
                        {selectedOpportunity && (
                            <>
                                <DialogHeader>
                                    <DialogTitle className="flex items-center gap-2">
                                        <Building2 className="h-5 w-5" />
                                        {selectedOpportunity.businessName}
                                    </DialogTitle>
                                    <DialogDescription>
                                        {selectedOpportunity.contactName} • {selectedOpportunity.email}
                                    </DialogDescription>
                                </DialogHeader>

                                <div className="space-y-4">
                                    {/* Deal Info */}
                                    <div className="grid grid-cols-3 gap-4">
                                        <div className="p-3 bg-secondary/50 rounded-lg">
                                            <div className="text-xs text-muted-foreground">Deal Value</div>
                                            <div className="text-lg font-bold text-green-500">
                                                {formatCurrency(selectedOpportunity.value)}
                                            </div>
                                        </div>
                                        <div className="p-3 bg-secondary/50 rounded-lg">
                                            <div className="text-xs text-muted-foreground">Probability</div>
                                            <div className="text-lg font-bold">{selectedOpportunity.probability}%</div>
                                        </div>
                                        <div className="p-3 bg-secondary/50 rounded-lg">
                                            <div className="text-xs text-muted-foreground">Stage</div>
                                            <div className="text-lg font-bold capitalize">
                                                {selectedOpportunity.stage.replace('_', ' ')}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Move Stage */}
                                    <div>
                                        <div className="text-sm font-medium mb-2">Move to Stage</div>
                                        <div className="flex flex-wrap gap-2">
                                            {stages.map((stage) => (
                                                <Button
                                                    key={stage.id}
                                                    variant={selectedOpportunity.stage === stage.id ? "default" : "outline"}
                                                    size="sm"
                                                    onClick={() => handleMoveStage(selectedOpportunity.id, stage.id as Opportunity['stage'])}
                                                >
                                                    <div className={`w-2 h-2 rounded-full ${stage.color} mr-2`} />
                                                    {stage.name}
                                                </Button>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Notes */}
                                    <div>
                                        <div className="flex items-center justify-between mb-2">
                                            <div className="text-sm font-medium">Notes</div>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => setNoteDialogOpen(true)}
                                            >
                                                <Plus className="h-4 w-4 mr-1" />
                                                Add Note
                                            </Button>
                                        </div>
                                        <div className="space-y-2 max-h-48 overflow-y-auto">
                                            {selectedOpportunity.notes.map((note, i) => (
                                                <div key={i} className="p-2 bg-secondary/50 rounded text-sm">
                                                    {note}
                                                </div>
                                            ))}
                                            {selectedOpportunity.notes.length === 0 && (
                                                <div className="text-muted-foreground text-sm">No notes yet</div>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                <DialogFooter>
                                    <Link to={`/leads/${selectedOpportunity.leadId}`}>
                                        <Button variant="outline">
                                            <ExternalLink className="h-4 w-4 mr-2" />
                                            View Lead Details
                                        </Button>
                                    </Link>
                                </DialogFooter>
                            </>
                        )}
                    </DialogContent>
                </Dialog>

                {/* Add Note Dialog */}
                <Dialog open={noteDialogOpen} onOpenChange={setNoteDialogOpen}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Add Note</DialogTitle>
                            <DialogDescription>
                                Add a note to {selectedOpportunity?.businessName}
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
                            <Button onClick={handleAddNote}>
                                Save Note
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </DashboardLayout>
    );
}
