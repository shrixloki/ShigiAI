import { useState } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { toast } from 'sonner';
import {
    Users,
    Shield,
    Mail,
    Database,
    Webhook,
    FileSpreadsheet,
    Download,
    Upload,
    Plus,
    Trash2,
    Edit,
    Key,
    Globe,
    Lock,
    AlertTriangle,
    CheckCircle2
} from 'lucide-react';

interface User {
    id: string;
    name: string;
    email: string;
    role: 'admin' | 'reviewer' | 'sender';
    status: 'active' | 'inactive';
    lastActive: string;
}

interface Webhook {
    id: string;
    name: string;
    url: string;
    events: string[];
    enabled: boolean;
}

const sampleUsers: User[] = [
    { id: '1', name: 'Admin User', email: 'admin@company.com', role: 'admin', status: 'active', lastActive: new Date().toISOString() },
    { id: '2', name: 'Review Manager', email: 'reviewer@company.com', role: 'reviewer', status: 'active', lastActive: new Date(Date.now() - 3600000).toISOString() },
    { id: '3', name: 'Outreach Sender', email: 'sender@company.com', role: 'sender', status: 'active', lastActive: new Date(Date.now() - 86400000).toISOString() },
];

const sampleWebhooks: Webhook[] = [
    { id: '1', name: 'CRM Integration', url: 'https://api.example.com/webhook', events: ['lead.created', 'lead.approved'], enabled: true },
    { id: '2', name: 'Slack Notifications', url: 'https://hooks.slack.com/...', events: ['email.replied'], enabled: true },
];

export default function Settings() {
    const [users, setUsers] = useState<User[]>(sampleUsers);
    const [webhooks, setWebhooks] = useState<Webhook[]>(sampleWebhooks);
    const [addUserDialogOpen, setAddUserDialogOpen] = useState(false);
    const [newUser, setNewUser] = useState({ name: '', email: '', role: 'sender' as User['role'] });

    // Email settings
    const [emailSettings, setEmailSettings] = useState({
        maxEmailsPerDay: 20,
        maxEmailsPerHour: 5,
        sendingDelay: 60,
        bounceThreshold: 3,
        unsubscribeEnabled: true,
        domainWarmup: true
    });

    // Sync settings
    const [syncSettings, setSyncSettings] = useState({
        googleSheetsEnabled: false,
        sheetsUrl: '',
        syncInterval: 60,
        conflictResolution: 'prefer_local'
    });

    const handleAddUser = () => {
        if (!newUser.name || !newUser.email) {
            toast.error('Please fill in all fields');
            return;
        }

        const user: User = {
            id: Date.now().toString(),
            ...newUser,
            status: 'active',
            lastActive: new Date().toISOString()
        };

        setUsers([...users, user]);
        setNewUser({ name: '', email: '', role: 'sender' });
        setAddUserDialogOpen(false);
        toast.success('User added successfully');
    };

    const handleDeleteUser = (userId: string) => {
        setUsers(users.filter(u => u.id !== userId));
        toast.success('User removed');
    };

    const handleToggleWebhook = (webhookId: string) => {
        setWebhooks(webhooks.map(w => {
            if (w.id === webhookId) {
                return { ...w, enabled: !w.enabled };
            }
            return w;
        }));
    };

    const getRoleBadge = (role: User['role']) => {
        switch (role) {
            case 'admin':
                return <Badge variant="error">Admin</Badge>;
            case 'reviewer':
                return <Badge variant="warning">Reviewer</Badge>;
            case 'sender':
                return <Badge variant="success">Sender</Badge>;
        }
    };

    const handleExportCSV = () => {
        toast.success('Exporting leads to CSV...');
        // Simulate export
        setTimeout(() => toast.success('Export complete! Check your downloads.'), 1500);
    };

    const handleImportCSV = () => {
        toast.info('CSV import dialog would open here');
    };

    return (
        <DashboardLayout>
            <div className="p-6 space-y-6">
                <PageHeader
                    title="Settings"
                    description="Manage users, integrations, and system configuration"
                />

                <Tabs defaultValue="users" className="space-y-6">
                    <TabsList>
                        <TabsTrigger value="users" className="flex items-center gap-2">
                            <Users className="h-4 w-4" />
                            Users & Roles
                        </TabsTrigger>
                        <TabsTrigger value="email" className="flex items-center gap-2">
                            <Mail className="h-4 w-4" />
                            Email Settings
                        </TabsTrigger>
                        <TabsTrigger value="sync" className="flex items-center gap-2">
                            <FileSpreadsheet className="h-4 w-4" />
                            Sync & Import
                        </TabsTrigger>
                        <TabsTrigger value="webhooks" className="flex items-center gap-2">
                            <Webhook className="h-4 w-4" />
                            Webhooks
                        </TabsTrigger>
                        <TabsTrigger value="compliance" className="flex items-center gap-2">
                            <Shield className="h-4 w-4" />
                            Compliance
                        </TabsTrigger>
                    </TabsList>

                    {/* Users & Roles Tab */}
                    <TabsContent value="users">
                        <Card>
                            <CardHeader>
                                <div className="flex items-center justify-between">
                                    <div>
                                        <CardTitle>Team Members</CardTitle>
                                        <CardDescription>Manage user access and permissions</CardDescription>
                                    </div>
                                    <Dialog open={addUserDialogOpen} onOpenChange={setAddUserDialogOpen}>
                                        <DialogTrigger asChild>
                                            <Button>
                                                <Plus className="h-4 w-4 mr-2" />
                                                Add User
                                            </Button>
                                        </DialogTrigger>
                                        <DialogContent>
                                            <DialogHeader>
                                                <DialogTitle>Add Team Member</DialogTitle>
                                                <DialogDescription>
                                                    Add a new user and assign their role
                                                </DialogDescription>
                                            </DialogHeader>
                                            <div className="space-y-4 py-4">
                                                <div className="space-y-2">
                                                    <Label>Name</Label>
                                                    <Input
                                                        placeholder="John Doe"
                                                        value={newUser.name}
                                                        onChange={(e) => setNewUser({ ...newUser, name: e.target.value })}
                                                    />
                                                </div>
                                                <div className="space-y-2">
                                                    <Label>Email</Label>
                                                    <Input
                                                        type="email"
                                                        placeholder="john@company.com"
                                                        value={newUser.email}
                                                        onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                                                    />
                                                </div>
                                                <div className="space-y-2">
                                                    <Label>Role</Label>
                                                    <Select
                                                        value={newUser.role}
                                                        onValueChange={(v) => setNewUser({ ...newUser, role: v as User['role'] })}
                                                    >
                                                        <SelectTrigger>
                                                            <SelectValue />
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            <SelectItem value="admin">Admin - Full access</SelectItem>
                                                            <SelectItem value="reviewer">Reviewer - Review & approve leads</SelectItem>
                                                            <SelectItem value="sender">Sender - Send emails only</SelectItem>
                                                        </SelectContent>
                                                    </Select>
                                                </div>
                                            </div>
                                            <DialogFooter>
                                                <Button variant="outline" onClick={() => setAddUserDialogOpen(false)}>
                                                    Cancel
                                                </Button>
                                                <Button onClick={handleAddUser}>Add User</Button>
                                            </DialogFooter>
                                        </DialogContent>
                                    </Dialog>
                                </div>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-3">
                                    {users.map((user) => (
                                        <div
                                            key={user.id}
                                            className="flex items-center justify-between p-4 bg-secondary/50 rounded-lg"
                                        >
                                            <div className="flex items-center gap-3">
                                                <Avatar>
                                                    <AvatarFallback className="bg-primary/20 text-primary">
                                                        {user.name.split(' ').map(n => n[0]).join('')}
                                                    </AvatarFallback>
                                                </Avatar>
                                                <div>
                                                    <div className="font-medium">{user.name}</div>
                                                    <div className="text-sm text-muted-foreground">{user.email}</div>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-3">
                                                {getRoleBadge(user.role)}
                                                <Button variant="ghost" size="icon">
                                                    <Edit className="h-4 w-4" />
                                                </Button>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => handleDeleteUser(user.id)}
                                                >
                                                    <Trash2 className="h-4 w-4" />
                                                </Button>
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {/* Role Permissions Info */}
                                <div className="mt-6 pt-6 border-t">
                                    <h4 className="text-sm font-medium mb-4">Role Permissions</h4>
                                    <div className="grid grid-cols-3 gap-4 text-sm">
                                        <div className="p-3 bg-red-500/10 rounded-lg">
                                            <div className="font-medium text-red-500 mb-2">Admin</div>
                                            <ul className="space-y-1 text-muted-foreground">
                                                <li>• Full system access</li>
                                                <li>• Manage users</li>
                                                <li>• Configure settings</li>
                                                <li>• Delete data</li>
                                            </ul>
                                        </div>
                                        <div className="p-3 bg-yellow-500/10 rounded-lg">
                                            <div className="font-medium text-yellow-500 mb-2">Reviewer</div>
                                            <ul className="space-y-1 text-muted-foreground">
                                                <li>• Review leads</li>
                                                <li>• Approve/reject</li>
                                                <li>• View analytics</li>
                                                <li>• Add notes</li>
                                            </ul>
                                        </div>
                                        <div className="p-3 bg-green-500/10 rounded-lg">
                                            <div className="font-medium text-green-500 mb-2">Sender</div>
                                            <ul className="space-y-1 text-muted-foreground">
                                                <li>• Send emails</li>
                                                <li>• View approved leads</li>
                                                <li>• Track responses</li>
                                                <li>• View own activity</li>
                                            </ul>
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Email Settings Tab */}
                    <TabsContent value="email">
                        <Card>
                            <CardHeader>
                                <CardTitle>Email Configuration</CardTitle>
                                <CardDescription>Configure rate limits and sending behavior</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="grid grid-cols-2 gap-6">
                                    <div className="space-y-2">
                                        <Label>Max Emails Per Day</Label>
                                        <Input
                                            type="number"
                                            value={emailSettings.maxEmailsPerDay}
                                            onChange={(e) => setEmailSettings({ ...emailSettings, maxEmailsPerDay: parseInt(e.target.value) })}
                                        />
                                        <p className="text-xs text-muted-foreground">Daily sending limit to avoid spam filters</p>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Max Emails Per Hour</Label>
                                        <Input
                                            type="number"
                                            value={emailSettings.maxEmailsPerHour}
                                            onChange={(e) => setEmailSettings({ ...emailSettings, maxEmailsPerHour: parseInt(e.target.value) })}
                                        />
                                        <p className="text-xs text-muted-foreground">Hourly rate limit</p>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Sending Delay (seconds)</Label>
                                        <Input
                                            type="number"
                                            value={emailSettings.sendingDelay}
                                            onChange={(e) => setEmailSettings({ ...emailSettings, sendingDelay: parseInt(e.target.value) })}
                                        />
                                        <p className="text-xs text-muted-foreground">Delay between emails</p>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Bounce Threshold</Label>
                                        <Input
                                            type="number"
                                            value={emailSettings.bounceThreshold}
                                            onChange={(e) => setEmailSettings({ ...emailSettings, bounceThreshold: parseInt(e.target.value) })}
                                        />
                                        <p className="text-xs text-muted-foreground">Stop sending after X bounces</p>
                                    </div>
                                </div>

                                <div className="space-y-4">
                                    <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-lg">
                                        <div>
                                            <div className="font-medium">Unsubscribe Links</div>
                                            <div className="text-sm text-muted-foreground">Include unsubscribe link in all emails</div>
                                        </div>
                                        <Switch
                                            checked={emailSettings.unsubscribeEnabled}
                                            onCheckedChange={(v) => setEmailSettings({ ...emailSettings, unsubscribeEnabled: v })}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-lg">
                                        <div>
                                            <div className="font-medium">Domain Warm-up Mode</div>
                                            <div className="text-sm text-muted-foreground">Gradually increase sending volume</div>
                                        </div>
                                        <Switch
                                            checked={emailSettings.domainWarmup}
                                            onCheckedChange={(v) => setEmailSettings({ ...emailSettings, domainWarmup: v })}
                                        />
                                    </div>
                                </div>

                                <Button onClick={() => toast.success('Email settings saved')}>
                                    Save Email Settings
                                </Button>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Sync & Import Tab */}
                    <TabsContent value="sync">
                        <div className="grid gap-6">
                            <Card>
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <FileSpreadsheet className="h-5 w-5" />
                                        Google Sheets Integration
                                    </CardTitle>
                                    <CardDescription>Two-way sync with Google Sheets</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-lg">
                                        <div>
                                            <div className="font-medium">Enable Google Sheets Sync</div>
                                            <div className="text-sm text-muted-foreground">Automatically sync leads with a spreadsheet</div>
                                        </div>
                                        <Switch
                                            checked={syncSettings.googleSheetsEnabled}
                                            onCheckedChange={(v) => setSyncSettings({ ...syncSettings, googleSheetsEnabled: v })}
                                        />
                                    </div>

                                    {syncSettings.googleSheetsEnabled && (
                                        <>
                                            <div className="space-y-2">
                                                <Label>Google Sheets URL</Label>
                                                <Input
                                                    placeholder="https://docs.google.com/spreadsheets/d/..."
                                                    value={syncSettings.sheetsUrl}
                                                    onChange={(e) => setSyncSettings({ ...syncSettings, sheetsUrl: e.target.value })}
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Sync Interval (minutes)</Label>
                                                <Select
                                                    value={syncSettings.syncInterval.toString()}
                                                    onValueChange={(v) => setSyncSettings({ ...syncSettings, syncInterval: parseInt(v) })}
                                                >
                                                    <SelectTrigger>
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="15">Every 15 minutes</SelectItem>
                                                        <SelectItem value="30">Every 30 minutes</SelectItem>
                                                        <SelectItem value="60">Every hour</SelectItem>
                                                        <SelectItem value="360">Every 6 hours</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Conflict Resolution</Label>
                                                <Select
                                                    value={syncSettings.conflictResolution}
                                                    onValueChange={(v) => setSyncSettings({ ...syncSettings, conflictResolution: v })}
                                                >
                                                    <SelectTrigger>
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="prefer_local">Prefer Local Data</SelectItem>
                                                        <SelectItem value="prefer_remote">Prefer Sheets Data</SelectItem>
                                                        <SelectItem value="newest">Keep Newest</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        </>
                                    )}
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <CardTitle>CSV Import/Export</CardTitle>
                                    <CardDescription>Bulk import or export lead data</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="flex gap-4">
                                        <Button variant="outline" onClick={handleImportCSV}>
                                            <Upload className="h-4 w-4 mr-2" />
                                            Import CSV
                                        </Button>
                                        <Button variant="outline" onClick={handleExportCSV}>
                                            <Download className="h-4 w-4 mr-2" />
                                            Export CSV
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    </TabsContent>

                    {/* Webhooks Tab */}
                    <TabsContent value="webhooks">
                        <Card>
                            <CardHeader>
                                <div className="flex items-center justify-between">
                                    <div>
                                        <CardTitle>Webhooks</CardTitle>
                                        <CardDescription>Send events to external services</CardDescription>
                                    </div>
                                    <Button>
                                        <Plus className="h-4 w-4 mr-2" />
                                        Add Webhook
                                    </Button>
                                </div>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-3">
                                    {webhooks.map((webhook) => (
                                        <div
                                            key={webhook.id}
                                            className="flex items-center justify-between p-4 bg-secondary/50 rounded-lg"
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className={`p-2 rounded-lg ${webhook.enabled ? 'bg-green-500/20' : 'bg-gray-500/20'}`}>
                                                    <Globe className={`h-5 w-5 ${webhook.enabled ? 'text-green-500' : 'text-gray-500'}`} />
                                                </div>
                                                <div>
                                                    <div className="font-medium">{webhook.name}</div>
                                                    <div className="text-sm text-muted-foreground font-mono">{webhook.url}</div>
                                                    <div className="flex gap-1 mt-1">
                                                        {webhook.events.map(event => (
                                                            <Badge key={event} variant="neutral" className="text-xs">{event}</Badge>
                                                        ))}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <Switch
                                                    checked={webhook.enabled}
                                                    onCheckedChange={() => handleToggleWebhook(webhook.id)}
                                                />
                                                <Button variant="ghost" size="icon">
                                                    <Edit className="h-4 w-4" />
                                                </Button>
                                                <Button variant="ghost" size="icon">
                                                    <Trash2 className="h-4 w-4" />
                                                </Button>
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                <div className="mt-6 pt-6 border-t">
                                    <h4 className="text-sm font-medium mb-3">Available Events</h4>
                                    <div className="grid grid-cols-3 gap-2 text-sm">
                                        <div className="flex items-center gap-2 text-muted-foreground">
                                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                                            lead.created
                                        </div>
                                        <div className="flex items-center gap-2 text-muted-foreground">
                                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                                            lead.approved
                                        </div>
                                        <div className="flex items-center gap-2 text-muted-foreground">
                                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                                            lead.rejected
                                        </div>
                                        <div className="flex items-center gap-2 text-muted-foreground">
                                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                                            email.sent
                                        </div>
                                        <div className="flex items-center gap-2 text-muted-foreground">
                                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                                            email.replied
                                        </div>
                                        <div className="flex items-center gap-2 text-muted-foreground">
                                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                                            email.bounced
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Compliance Tab */}
                    <TabsContent value="compliance">
                        <div className="grid gap-6">
                            <Card>
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <Shield className="h-5 w-5" />
                                        Compliance & Risk Controls
                                    </CardTitle>
                                    <CardDescription>Ensure safe and compliant outreach</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="flex items-center justify-between p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
                                        <div className="flex items-center gap-3">
                                            <CheckCircle2 className="h-5 w-5 text-green-500" />
                                            <div>
                                                <div className="font-medium">Unsubscribe Links</div>
                                                <div className="text-sm text-muted-foreground">All emails include unsubscribe option</div>
                                            </div>
                                        </div>
                                        <Badge variant="success">Active</Badge>
                                    </div>

                                    <div className="flex items-center justify-between p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
                                        <div className="flex items-center gap-3">
                                            <Lock className="h-5 w-5 text-green-500" />
                                            <div>
                                                <div className="font-medium">Do-Not-Contact Registry</div>
                                                <div className="text-sm text-muted-foreground">Automatically checks and respects opt-outs</div>
                                            </div>
                                        </div>
                                        <Badge variant="success">Active</Badge>
                                    </div>

                                    <div className="flex items-center justify-between p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                                        <div className="flex items-center gap-3">
                                            <AlertTriangle className="h-5 w-5 text-yellow-500" />
                                            <div>
                                                <div className="font-medium">Spam Risk Scoring</div>
                                                <div className="text-sm text-muted-foreground">Monitor and manage spam risk levels</div>
                                            </div>
                                        </div>
                                        <Badge variant="warning">Low Risk</Badge>
                                    </div>

                                    <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-lg">
                                        <div>
                                            <div className="font-medium">Rate Limiting</div>
                                            <div className="text-sm text-muted-foreground">Automatic sending limits enforced</div>
                                        </div>
                                        <div className="text-right">
                                            <div className="font-medium">20/day, 5/hour</div>
                                            <div className="text-xs text-muted-foreground">Current limits</div>
                                        </div>
                                    </div>

                                    <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-lg">
                                        <div>
                                            <div className="font-medium">Domain Warm-up</div>
                                            <div className="text-sm text-muted-foreground">Gradually increasing sending volume</div>
                                        </div>
                                        <div className="text-right">
                                            <div className="font-medium">Day 5 of 14</div>
                                            <div className="text-xs text-muted-foreground">Warm-up progress</div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    </TabsContent>
                </Tabs>
            </div>
        </DashboardLayout>
    );
}
