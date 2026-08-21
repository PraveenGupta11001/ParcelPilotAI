import { cn } from "../../lib/utils";

export const Button = ({ className, variant = "primary", size = "md", children, ...props }: { className?: string; variant?: string; size?: string; children?: any;[x: string]: any }) => {
    const variants = {
        primary: "bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/15",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border",
        ghost: "bg-transparent text-muted-foreground hover:bg-secondary/70 hover:text-foreground",
        danger: "bg-rose-500 text-white hover:bg-rose-600 shadow-lg shadow-rose-500/15",
        success: "bg-emerald-500 text-white hover:bg-emerald-600 shadow-lg shadow-emerald-500/15",
        outline: "bg-background/60 text-foreground border border-border hover:bg-secondary/70",
    };
    const sizes = {
        sm: "h-9 px-3 text-xs rounded-lg",
        md: "h-11 px-4 text-sm rounded-xl",
        lg: "h-12 px-5 text-sm rounded-xl",
        icon: "h-10 w-10 rounded-xl p-0",
    };

    return (
        <button
            className={cn(
                "inline-flex items-center justify-center gap-2 font-bold transition-all active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
                (variants as any)[variant],
                (sizes as any)[size],
                className
            )}
            {...props}
        >
            {children}
        </button>
    );
};
