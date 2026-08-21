import { cn } from "../../lib/utils";

export const Card = ({ className, children, ...props }: { className?: string; children?: any;[x: string]: any }) => (
    <div
        className={cn(
            "rounded-xl border border-border bg-card text-card-foreground shadow-sm",
            className
        )}
        {...props}
    >
        {children}
    </div>
);
