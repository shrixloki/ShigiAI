import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Activity,
  Users,
  Server,
  Mail,
  ChevronRight
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ThemeToggle } from '@/components/ThemeToggle';

interface DashboardLayoutProps {
  children: ReactNode;
}

const navigation = [
  { name: 'Overview', href: '/', icon: LayoutDashboard },
  { name: 'Activity Logs', href: '/activity', icon: Activity },
  { name: 'Leads', href: '/leads', icon: Users },
  { name: 'Email Templates', href: '/email-templates', icon: Mail },
  { name: 'System Health', href: '/health', icon: Server },
];

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const location = useLocation();

  return (
    <div className="flex min-h-screen w-full bg-background">
      {/* Sidebar */}
      <aside className="w-56 border-r border-border bg-card flex flex-col">
        <div className="p-4 border-b border-border">
          <h1 className="text-lg font-bold text-foreground tracking-tight bg-gradient-to-r from-primary to-blue-500 bg-clip-text text-transparent">
            ShigiAI
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Cold Outreach Agent
          </p>
        </div>

        <nav className="flex-1 p-2">
          <ul className="space-y-1">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href;
              return (
                <li key={item.name}>
                  <Link
                    to={item.href}
                    className={cn(
                      'flex items-center gap-2 px-3 py-2 text-sm rounded-md transition-colors',
                      isActive
                        ? 'bg-secondary text-foreground font-medium'
                        : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50'
                    )}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.name}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="p-4 border-t border-border flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            v1.0.0
          </p>
          <ThemeToggle />
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
