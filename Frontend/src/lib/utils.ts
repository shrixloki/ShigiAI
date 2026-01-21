import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { format, formatDistanceToNow } from 'date-fns';

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

export function formatDateTime(date: string | Date | number): string {
    try {
        const d = new Date(date);
        // Check if valid date
        if (isNaN(d.getTime())) {
            return 'Invalid Date';
        }
        return format(d, 'PPpp'); // Aug 29, 2023 12:00 PM
    } catch (error) {
        return 'Invalid Date';
    }
}

export function getRelativeTime(date: string | Date | number): string {
    try {
        const d = new Date(date);
        if (isNaN(d.getTime())) {
            return 'Unknown time';
        }
        return formatDistanceToNow(d, { addSuffix: true });
    } catch (error) {
        return 'Unknown time';
    }
}
