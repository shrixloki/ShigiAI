import { cn } from '@/lib/utils';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon?: LucideIcon;
  description?: string;
  className?: string;
}

export function StatCard({ title, value, icon: Icon, description, className }: StatCardProps) {
  return (
    <div className={cn('bg-card border border-border rounded-lg p-4', className)}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            {title}
          </p>
          <p className="text-2xl font-semibold text-foreground mt-1">
            {value}
          </p>
          {description && (
            <p className="text-xs text-muted-foreground mt-1">
              {description}
            </p>
          )}
        </div>
        {Icon && (
          <div className="p-2 bg-secondary rounded">
            <Icon className="h-4 w-4 text-muted-foreground" />
          </div>
        )}
      </div>
    </div>
  );
}
