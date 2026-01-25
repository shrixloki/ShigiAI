import { useState } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from '@/components/ui/dialog';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import {
    Plus,
    Mail,
    Clock,
    Play,
    Pause,
    Settings2,
    ArrowRight,
    CheckCircle2,
    AlertCircle,
    Edit,
    Trash2,
    Copy
} from 'lucide-react';

interface CampaignStep {
    id: string;
    order: number;
    type: 'initial' | 'followup' | 'final';
    subject: string;
    delayDays: number;
    enabled: boolean;
}

interface Campaign {
    id: string;
    name: string;
    status: 'active' | 'paused' | 'draft';
    steps: CampaignStep[];
    leadsCount: number;
    sentCount: number;
    replyCount: number;
    createdAt: string;
}

// Default campaigns (will be replaced with API data)
const defaultCampaigns: Campaign[] = [
    {
        id: '1',
        name: 'Initial Outreach Sequence',
        status: 'active',
        steps: [
            { id: '1', order: 1, type: 'initial', subject: 'Quick question about {{business_name}}', delayDays: 0, enabled: true },
            { id: '2', order: 2, type: 'followup', subject: 'Following up - {{business_name}}', delayDays: 3, enabled: true },
            { id: '3', order: 3, type: 'final', subject: 'Last attempt to connect', delayDays: 7, enabled: true },
        ],
        leadsCount: 45,
        sentCount: 120,
        replyCount: 8,
        createdAt: new Date().toISOString()
    }
];

export default function Campaigns() {
    const queryClient = useQueryClient();
    const [campaigns, setCampaigns] = useState<Campaign[]>(defaultCampaigns);
    const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null);
    const [createDialogOpen, setCreateDialogOpen] = useState(false);
    const [newCampaignName, setNewCampaignName] = useState('');

    const { data: overview } = useQuery({
        queryKey: ['overview'],
        queryFn: api.getOverview,
        refetchInterval: 10000
    });

    const handleCreateCampaign = () => {
        if (!newCampaignName.trim()) {
            toast.error('Please enter a campaign name');
            return;
        }

        const newCampaign: Campaign = {
            id: Date.now().toString(),
            name: newCampaignName,
            status: 'draft',
            steps: [
                { id: '1', order: 1, type: 'initial', subject: 'Quick question about {{business_name}}', delayDays: 0, enabled: true },
            ],
            leadsCount: 0,
            sentCount: 0,
            replyCount: 0,
            createdAt: new Date().toISOString()
        };

        setCampaigns([...campaigns, newCampaign]);
        setNewCampaignName('');
        setCreateDialogOpen(false);
        toast.success('Campaign created successfully');
    };

    const handleToggleCampaign = (campaignId: string) => {
        setCampaigns(campaigns.map(c => {
            if (c.id === campaignId) {
                const newStatus = c.status === 'active' ? 'paused' : 'active';
                toast.success(`Campaign ${newStatus === 'active' ? 'activated' : 'paused'}`);
                return { ...c, status: newStatus };
            }
            return c;
        }));
    };

    const handleAddStep = (campaignId: string) => {
        setCampaigns(campaigns.map(c => {
            if (c.id === campaignId) {
                const newOrder = c.steps.length + 1;
                const newStep: CampaignStep = {
                    id: Date.now().toString(),
                    order: newOrder,
                    type: newOrder === 1 ? 'initial' : newOrder === 2 ? 'followup' : 'final',
                    subject: `Follow-up ${newOrder} - {{business_name}}`,
                    delayDays: newOrder * 3,
                    enabled: true
                };
                return { ...c, steps: [...c.steps, newStep] };
            }
            return c;
        }));
        toast.success('Step added to campaign');
    };

    const handleDeleteStep = (campaignId: string, stepId: string) => {
        setCampaigns(campaigns.map(c => {
            if (c.id === campaignId) {
                return { ...c, steps: c.steps.filter(s => s.id !== stepId) };
            }
            return c;
        }));
        toast.success('Step removed');
    };

    const getStatusBadge = (status: Campaign['status']) => {
        switch (status) {
            case 'active':
                return <Badge variant="success">Active</Badge>;
            case 'paused':
                return <Badge variant="warning">Paused</Badge>;
            case 'draft':
                return <Badge variant="neutral">Draft</Badge>;
        }
    };

    const getStepTypeBadge = (type: CampaignStep['type']) => {
        switch (type) {
            case 'initial':
                return <Badge variant="pending">Initial</Badge>;
            case 'followup':
                return <Badge variant="warning">Follow-up</Badge>;
            case 'final':
                return <Badge variant="error">Final</Badge>;
        }
    };

    return (
        <DashboardLayout>
            <div className="p-6 space-y-6">
                <div className="flex justify-between items-center">
                    <PageHeader
                        title="Email Campaigns"
                        description="Manage multi-step email sequences with conditional logic"
                    />
                    <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                        <DialogTrigger asChild>
                            <Button>
                                <Plus className="h-4 w-4 mr-2" />
                                New Campaign
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>Create New Campaign</DialogTitle>
                                <DialogDescription>
                                    Create a multi-step email sequence for your outreach
                                </DialogDescription>
                            </DialogHeader>
                            <div className="space-y-4 py-4">
                                <div className="space-y-2">
                                    <Label>Campaign Name</Label>
                                    <Input
                                        placeholder="e.g., Tech Startups Outreach"
                                        value={newCampaignName}
                                        onChange={(e) => setNewCampaignName(e.target.value)}
                                    />
                                </div>
                            </div>
                            <DialogFooter>
                                <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
                                    Cancel
                                </Button>
                                <Button onClick={handleCreateCampaign}>
                                    Create Campaign
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>

                {/* Campaign List */}
                <div className="grid gap-6">
                    {campaigns.map((campaign) => (
                        <Card key={campaign.id}>
                            <CardHeader>
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <CardTitle className="text-lg">{campaign.name}</CardTitle>
                                        {getStatusBadge(campaign.status)}
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => handleToggleCampaign(campaign.id)}
                                        >
                                            {campaign.status === 'active' ? (
                                                <>
                                                    <Pause className="h-4 w-4 mr-1" />
                                                    Pause
                                                </>
                                            ) : (
                                                <>
                                                    <Play className="h-4 w-4 mr-1" />
                                                    Activate
                                                </>
                                            )}
                                        </Button>
                                        <Button variant="outline" size="sm">
                                            <Settings2 className="h-4 w-4" />
                                        </Button>
                                    </div>
                                </div>
                                <CardDescription className="flex items-center gap-4 mt-2">
                                    <span>{campaign.leadsCount} leads enrolled</span>
                                    <span>•</span>
                                    <span>{campaign.sentCount} emails sent</span>
                                    <span>•</span>
                                    <span className="text-green-500">{campaign.replyCount} replies</span>
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                {/* Campaign Steps */}
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <h4 className="text-sm font-medium">Sequence Steps</h4>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => handleAddStep(campaign.id)}
                                            disabled={campaign.steps.length >= 5}
                                        >
                                            <Plus className="h-4 w-4 mr-1" />
                                            Add Step
                                        </Button>
                                    </div>

                                    <div className="space-y-2">
                                        {campaign.steps.map((step, index) => (
                                            <div
                                                key={step.id}
                                                className="flex items-center gap-3 p-3 bg-secondary/50 rounded-lg"
                                            >
                                                <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/20 text-primary font-bold text-sm">
                                                    {step.order}
                                                </div>

                                                <div className="flex-1">
                                                    <div className="flex items-center gap-2">
                                                        {getStepTypeBadge(step.type)}
                                                        <span className="text-sm font-medium">{step.subject}</span>
                                                    </div>
                                                    <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                                                        <Clock className="h-3 w-3" />
                                                        {step.delayDays === 0 ? 'Send immediately' : `Wait ${step.delayDays} days`}
                                                    </div>
                                                </div>

                                                {index < campaign.steps.length - 1 && (
                                                    <ArrowRight className="h-4 w-4 text-muted-foreground" />
                                                )}

                                                <div className="flex items-center gap-1">
                                                    <Switch checked={step.enabled} />
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-8 w-8"
                                                        onClick={() => handleDeleteStep(campaign.id, step.id)}
                                                    >
                                                        <Trash2 className="h-4 w-4 text-muted-foreground" />
                                                    </Button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Campaign Settings */}
                                <div className="mt-4 pt-4 border-t">
                                    <h4 className="text-sm font-medium mb-3">Automation Rules</h4>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="flex items-center justify-between p-3 bg-secondary/30 rounded-lg">
                                            <div className="flex items-center gap-2">
                                                <CheckCircle2 className="h-4 w-4 text-green-500" />
                                                <span className="text-sm">Auto-pause on reply</span>
                                            </div>
                                            <Switch defaultChecked />
                                        </div>
                                        <div className="flex items-center justify-between p-3 bg-secondary/30 rounded-lg">
                                            <div className="flex items-center gap-2">
                                                <AlertCircle className="h-4 w-4 text-yellow-500" />
                                                <span className="text-sm">Handle bounces</span>
                                            </div>
                                            <Switch defaultChecked />
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>

                {campaigns.length === 0 && (
                    <Card className="p-12 text-center">
                        <Mail className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                        <h3 className="text-lg font-medium mb-2">No campaigns yet</h3>
                        <p className="text-muted-foreground mb-4">
                            Create your first multi-step email campaign to start automated outreach
                        </p>
                        <Button onClick={() => setCreateDialogOpen(true)}>
                            <Plus className="h-4 w-4 mr-2" />
                            Create Campaign
                        </Button>
                    </Card>
                )}
            </div>
        </DashboardLayout>
    );
}
