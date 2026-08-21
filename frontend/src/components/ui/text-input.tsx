import { cn } from "../../lib/utils";

export const TextInput = ({ icon: Icon, className, inputClassName, ...props }: { icon?: any; className?: string; inputClassName?: string;[x: string]: any }) => (
    <div className={cn("relative group w-full", className)}>
        {Icon && <Icon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within:text-primary" />}
        <input
            className={cn(
                "h-11 w-full rounded-xl border border-border bg-input px-3 text-sm font-semibold text-foreground outline-none transition-all placeholder:text-muted-foreground/70 focus:border-primary focus:ring-4 focus:ring-primary/10",
                Icon && "pl-10",
                inputClassName
            )}
            {...props}
        />
    </div>
);
