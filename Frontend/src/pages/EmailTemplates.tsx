import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { api, EmailTemplate } from '@/lib/api';
import {
    Mail,
    Send,
    Save,
    RotateCcw,
    CheckCircle2,
    XCircle,
    AlertTriangle,
    Eye,
    Edit3,
    TestTube2,
    ChevronDown
} from 'lucide-react';
import { cn } from '@/lib/utils';

type TabType = 'templates' | 'test';

export default function EmailTemplates() {
    const queryClient = useQueryClient();
    const [activeTab, setActiveTab] = useState<TabType>('templates');
    const [selectedCategory, setSelectedCategory] = useState<string>('general');
    const [editMode, setEditMode] = useState(false);
    const [subjectTemplate, setSubjectTemplate] = useState('');
    const [textTemplate, setTextTemplate] = useState('');
    const [hasChanges, setHasChanges] = useState(false);

    // Test email state
    const [testEmail, setTestEmail] = useState('laukikxrajput@gmail.com');
    const [testSubject, setTestSubject] = useState('');
    const [testBody, setTestBody] = useState('');
    const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

    // Fetch templates
    const { data: templatesData, isLoading, error } = useQuery({
        queryKey: ['email-templates'],
        queryFn: api.getEmailTemplates,
        refetchInterval: 30000
    });

    const templates = templatesData?.templates || {};

    // Update template mutation
    const updateTemplateMutation = useMutation({
        mutationFn: ({ category, subject, text }: { category: string; subject: string; text: string }) =>
            api.updateEmailTemplate(category, subject, text),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['email-templates'] });
            setEditMode(false);
            setHasChanges(false);
        }
    });

    // Reset template mutation
    const resetTemplateMutation = useMutation({
        mutationFn: (category: string) => api.resetEmailTemplate(category),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['email-templates'] });
            setEditMode(false);
            setHasChanges(false);
        }
    });

    // Send test email mutation
    const sendTestEmailMutation = useMutation({
        mutationFn: ({ toEmail, subject, body, category }: { toEmail: string; subject: string; body: string; category: string }) =>
            api.sendTestEmail(toEmail, subject, body, category),
        onSuccess: (data) => {
            setTestResult({ success: true, message: data.message });
        },
        onError: (error: any) => {
            setTestResult({
                success: false,
                message: error?.response?.data?.detail || error.message || 'Failed to send test email'
            });
        }
    });

    // Load selected template into editor
    useEffect(() => {
        if (templates[selectedCategory]) {
            const template = templates[selectedCategory];
            setSubjectTemplate(template.subject_template);
            setTextTemplate(template.text_template);
            setHasChanges(false);

            // Also pre-fill test email fields with current template
            setTestSubject(template.subject_template.replace(/\{\{.*?\}\}/g, (match) => {
                const varName = match.replace(/[{}]/g, '');
                if (varName === 'business_name') return 'Test Business';
                if (varName === 'location') return 'Test City';
                if (varName === 'sender_name') return 'Your Name';
                return match;
            }));
            setTestBody(template.text_template.replace(/\{\{.*?\}\}/g, (match) => {
                const varName = match.replace(/[{}]/g, '');
                if (varName === 'business_name') return 'Test Business';
                if (varName === 'location') return 'Test City';
                if (varName === 'sender_name') return 'Your Name';
                return match;
            }));
        }
    }, [selectedCategory, templates]);

    const handleSubjectChange = (value: string) => {
        setSubjectTemplate(value);
        setHasChanges(true);
    };

    const handleTextChange = (value: string) => {
        setTextTemplate(value);
        setHasChanges(true);
    };

    const handleSave = () => {
        updateTemplateMutation.mutate({
            category: selectedCategory,
            subject: subjectTemplate,
            text: textTemplate
        });
    };

    const handleReset = () => {
        if (confirm('Reset this template to the default? Your custom changes will be lost.')) {
            resetTemplateMutation.mutate(selectedCategory);
        }
    };

    const handleSendTestEmail = () => {
        if (!testEmail || !testSubject || !testBody) {
            setTestResult({ success: false, message: 'Please fill in all fields' });
            return;
        }
        setTestResult(null);
        sendTestEmailMutation.mutate({
            toEmail: testEmail,
            subject: testSubject,
            body: testBody,
            category: selectedCategory
        });
    };

    const categoryLabels: Record<string, string> = {
        general: '🏢 General',
        restaurant: '🍽️ Restaurant',
        plumber: '🔧 Plumber/Contractor',
        salon: '💇 Salon/Spa',
        fitness: '💪 Gym/Fitness'
    };

    return (
        <DashboardLayout>
            <div className="p-6 space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
                            <Mail className="h-7 w-7 text-blue-500" />
                            Email Templates
                        </h1>
                        <p className="text-muted-foreground mt-1">
                            Customize outreach emails by business category and test email sending
                        </p>
                    </div>
                </div>

                {/* Tabs */}
                <div className="border-b border-border">
                    <nav className="flex gap-4">
                        <button
                            onClick={() => setActiveTab('templates')}
                            className={cn(
                                'px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2',
                                activeTab === 'templates'
                                    ? 'border-blue-500 text-blue-500'
                                    : 'border-transparent text-muted-foreground hover:text-foreground'
                            )}
                        >
                            <Edit3 className="h-4 w-4" />
                            Edit Templates
                        </button>
                        <button
                            onClick={() => setActiveTab('test')}
                            className={cn(
                                'px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2',
                                activeTab === 'test'
                                    ? 'border-blue-500 text-blue-500'
                                    : 'border-transparent text-muted-foreground hover:text-foreground'
                            )}
                        >
                            <TestTube2 className="h-4 w-4" />
                            Test Email
                        </button>
                    </nav>
                </div>

                {isLoading ? (
                    <div className="flex items-center justify-center py-12">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    </div>
                ) : error ? (
                    <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 flex items-center gap-2 text-red-400">
                        <XCircle className="h-5 w-5" />
                        Failed to load templates
                    </div>
                ) : (
                    <div className="grid grid-cols-12 gap-6">
                        {/* Category Selector */}
                        <div className="col-span-3">
                            <div className="bg-card border border-border rounded-lg p-4">
                                <h3 className="text-sm font-semibold text-foreground mb-3">Business Category</h3>
                                <div className="space-y-1">
                                    {Object.keys(templates).map((category) => {
                                        const template = templates[category];
                                        return (
                                            <button
                                                key={category}
                                                onClick={() => setSelectedCategory(category)}
                                                className={cn(
                                                    'w-full text-left px-3 py-2 rounded-md text-sm transition-colors flex items-center justify-between',
                                                    selectedCategory === category
                                                        ? 'bg-blue-500/10 text-blue-500 font-medium'
                                                        : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50'
                                                )}
                                            >
                                                <span>{categoryLabels[category] || category}</span>
                                                {template?.type === 'custom' && (
                                                    <span className="text-xs bg-purple-500/20 text-purple-400 px-1.5 py-0.5 rounded">
                                                        Custom
                                                    </span>
                                                )}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>

                        {/* Main Content */}
                        <div className="col-span-9">
                            {activeTab === 'templates' && (
                                <div className="bg-card border border-border rounded-lg">
                                    {/* Template Header */}
                                    <div className="p-4 border-b border-border flex items-center justify-between">
                                        <div>
                                            <h3 className="font-semibold text-foreground flex items-center gap-2">
                                                {templates[selectedCategory]?.name || selectedCategory}
                                                {templates[selectedCategory]?.type === 'custom' && (
                                                    <span className="text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded-full">
                                                        Customized
                                                    </span>
                                                )}
                                            </h3>
                                            <p className="text-xs text-muted-foreground mt-1">
                                                Variables: {'{{'} business_name {'}}'}, {'{{'} location {'}}'}, {'{{'} sender_name {'}}'}
                                            </p>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {!editMode ? (
                                                <button
                                                    onClick={() => setEditMode(true)}
                                                    className="px-3 py-1.5 bg-blue-500/10 text-blue-500 rounded-md text-sm font-medium hover:bg-blue-500/20 transition-colors flex items-center gap-1"
                                                >
                                                    <Edit3 className="h-4 w-4" />
                                                    Edit
                                                </button>
                                            ) : (
                                                <>
                                                    {templates[selectedCategory]?.type === 'custom' && (
                                                        <button
                                                            onClick={handleReset}
                                                            disabled={resetTemplateMutation.isPending}
                                                            className="px-3 py-1.5 bg-orange-500/10 text-orange-500 rounded-md text-sm font-medium hover:bg-orange-500/20 transition-colors flex items-center gap-1 disabled:opacity-50"
                                                        >
                                                            <RotateCcw className="h-4 w-4" />
                                                            Reset
                                                        </button>
                                                    )}
                                                    <button
                                                        onClick={() => {
                                                            setEditMode(false);
                                                            // Reload original template
                                                            if (templates[selectedCategory]) {
                                                                setSubjectTemplate(templates[selectedCategory].subject_template);
                                                                setTextTemplate(templates[selectedCategory].text_template);
                                                                setHasChanges(false);
                                                            }
                                                        }}
                                                        className="px-3 py-1.5 bg-secondary text-muted-foreground rounded-md text-sm font-medium hover:bg-secondary/80 transition-colors"
                                                    >
                                                        Cancel
                                                    </button>
                                                    <button
                                                        onClick={handleSave}
                                                        disabled={!hasChanges || updateTemplateMutation.isPending}
                                                        className="px-3 py-1.5 bg-green-500 text-white rounded-md text-sm font-medium hover:bg-green-600 transition-colors flex items-center gap-1 disabled:opacity-50"
                                                    >
                                                        <Save className="h-4 w-4" />
                                                        {updateTemplateMutation.isPending ? 'Saving...' : 'Save'}
                                                    </button>
                                                </>
                                            )}
                                        </div>
                                    </div>

                                    {/* Template Editor */}
                                    <div className="p-4 space-y-4">
                                        {/* Subject */}
                                        <div>
                                            <label className="block text-sm font-medium text-foreground mb-2">
                                                Subject Line
                                            </label>
                                            {editMode ? (
                                                <input
                                                    type="text"
                                                    value={subjectTemplate}
                                                    onChange={(e) => handleSubjectChange(e.target.value)}
                                                    className="w-full px-3 py-2 bg-background border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                    placeholder="Email subject template..."
                                                />
                                            ) : (
                                                <div className="px-3 py-2 bg-secondary/50 border border-border rounded-md text-foreground">
                                                    {subjectTemplate}
                                                </div>
                                            )}
                                        </div>

                                        {/* Body */}
                                        <div>
                                            <label className="block text-sm font-medium text-foreground mb-2">
                                                Email Body
                                            </label>
                                            {editMode ? (
                                                <textarea
                                                    value={textTemplate}
                                                    onChange={(e) => handleTextChange(e.target.value)}
                                                    rows={15}
                                                    className="w-full px-3 py-2 bg-background border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                                                    placeholder="Email body template..."
                                                />
                                            ) : (
                                                <pre className="px-3 py-2 bg-secondary/50 border border-border rounded-md text-foreground whitespace-pre-wrap font-mono text-sm overflow-auto max-h-96">
                                                    {textTemplate}
                                                </pre>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            )}

                            {activeTab === 'test' && (
                                <div className="bg-card border border-border rounded-lg">
                                    {/* Test Header */}
                                    <div className="p-4 border-b border-border">
                                        <h3 className="font-semibold text-foreground flex items-center gap-2">
                                            <TestTube2 className="h-5 w-5 text-purple-500" />
                                            Send Test Email
                                        </h3>
                                        <p className="text-xs text-muted-foreground mt-1">
                                            Test your email configuration by sending a real email
                                        </p>
                                    </div>

                                    {/* Test Form */}
                                    <div className="p-4 space-y-4">
                                        {/* Result Banner */}
                                        {testResult && (
                                            <div className={cn(
                                                'p-4 rounded-lg flex items-center gap-3',
                                                testResult.success
                                                    ? 'bg-green-500/10 border border-green-500/20'
                                                    : 'bg-red-500/10 border border-red-500/20'
                                            )}>
                                                {testResult.success ? (
                                                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                                                ) : (
                                                    <XCircle className="h-5 w-5 text-red-500" />
                                                )}
                                                <span className={testResult.success ? 'text-green-400' : 'text-red-400'}>
                                                    {testResult.message}
                                                </span>
                                            </div>
                                        )}

                                        {/* Warning */}
                                        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-4 flex items-start gap-3">
                                            <AlertTriangle className="h-5 w-5 text-yellow-500 shrink-0 mt-0.5" />
                                            <div className="text-sm text-yellow-400">
                                                <p className="font-medium">This will send a real email!</p>
                                                <p className="text-yellow-400/80 mt-1">
                                                    Make sure your SMTP credentials are configured correctly in the .env file.
                                                </p>
                                            </div>
                                        </div>

                                        {/* To Email */}
                                        <div>
                                            <label className="block text-sm font-medium text-foreground mb-2">
                                                Send To
                                            </label>
                                            <input
                                                type="email"
                                                value={testEmail}
                                                onChange={(e) => setTestEmail(e.target.value)}
                                                className="w-full px-3 py-2 bg-background border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                placeholder="recipient@email.com"
                                            />
                                        </div>

                                        {/* Subject */}
                                        <div>
                                            <label className="block text-sm font-medium text-foreground mb-2">
                                                Subject
                                            </label>
                                            <input
                                                type="text"
                                                value={testSubject}
                                                onChange={(e) => setTestSubject(e.target.value)}
                                                className="w-full px-3 py-2 bg-background border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                placeholder="Email subject..."
                                            />
                                        </div>

                                        {/* Body */}
                                        <div>
                                            <label className="block text-sm font-medium text-foreground mb-2">
                                                Email Body
                                            </label>
                                            <textarea
                                                value={testBody}
                                                onChange={(e) => setTestBody(e.target.value)}
                                                rows={10}
                                                className="w-full px-3 py-2 bg-background border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                                                placeholder="Email body..."
                                            />
                                        </div>

                                        {/* Preview from Template */}
                                        <button
                                            onClick={() => {
                                                if (templates[selectedCategory]) {
                                                    const template = templates[selectedCategory];
                                                    setTestSubject(template.subject_template.replace(/\{\{.*?\}\}/g, (match) => {
                                                        const varName = match.replace(/[{}]/g, '');
                                                        if (varName === 'business_name') return 'Test Business';
                                                        if (varName === 'location') return 'Test City';
                                                        if (varName === 'sender_name') return 'Your Name';
                                                        return match;
                                                    }));
                                                    setTestBody(template.text_template.replace(/\{\{.*?\}\}/g, (match) => {
                                                        const varName = match.replace(/[{}]/g, '');
                                                        if (varName === 'business_name') return 'Test Business';
                                                        if (varName === 'location') return 'Test City';
                                                        if (varName === 'sender_name') return 'Your Name';
                                                        return match;
                                                    }));
                                                }
                                            }}
                                            className="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1"
                                        >
                                            <Eye className="h-4 w-4" />
                                            Load from "{categoryLabels[selectedCategory] || selectedCategory}" template
                                        </button>

                                        {/* Send Button */}
                                        <button
                                            onClick={handleSendTestEmail}
                                            disabled={sendTestEmailMutation.isPending || !testEmail || !testSubject || !testBody}
                                            className="w-full py-3 bg-gradient-to-r from-blue-500 to-purple-500 text-white rounded-lg font-medium hover:from-blue-600 hover:to-purple-600 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {sendTestEmailMutation.isPending ? (
                                                <>
                                                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                                                    Sending...
                                                </>
                                            ) : (
                                                <>
                                                    <Send className="h-5 w-5" />
                                                    Send Test Email
                                                </>
                                            )}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </DashboardLayout>
    );
}
