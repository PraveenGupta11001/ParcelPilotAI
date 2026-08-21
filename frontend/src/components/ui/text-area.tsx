import { cn } from "../../lib/utils";

export const TextArea = ({ className, ...props }: { className?: string;[x: string]: any }) => (
    <textarea
        className={cn(
            "min-h-[120px] w-full rounded-xl border border-border bg-input p-3 text-sm font-semibold text-foreground outline-none transition-all placeholder:text-muted-foreground/70 focus:border-primary focus:ring-4 focus:ring-primary/10",
            className
        )}
        {...props}
    />
);
