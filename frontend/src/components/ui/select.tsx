import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Check, ChevronDown, Search } from "lucide-react";
import { cn } from "../../lib/utils";
import { TextInput } from "./text-input";

const DEFAULT_POSITION = { left: 0, top: 0, width: 0, maxHeight: 288 };

export const Select = ({ options = [], value, onChange, placeholder = "Select...", icon: Icon, className, searchable = false }: { options?: any[]; value: any; onChange: any; placeholder?: string; icon?: any; className?: string; searchable?: boolean }) => {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    const [position, setPosition] = useState(DEFAULT_POSITION);
    const ref = useRef<HTMLDivElement>(null);
    const buttonRef = useRef<HTMLButtonElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);

    const selected = useMemo(
        () => options.find((option) => String(option.value) === String(value)),
        [options, value]
    );

    const filtered = useMemo(() => {
        const clean = query.trim().toLowerCase();
        if (!clean) return options;
        return options.filter((option) =>
            [option.label, option.description].filter(Boolean).join(" ").toLowerCase().includes(clean)
        );
    }, [options, query]);

    const updatePosition = () => {
        const rect = buttonRef.current?.getBoundingClientRect();
        if (!rect) return;
        const margin = 8;
        const preferredHeight = 288;
        const spaceBelow = window.innerHeight - rect.bottom - margin;
        const spaceAbove = rect.top - margin;
        const openUp = spaceBelow < 180 && spaceAbove > spaceBelow;
        const maxHeight = Math.max(160, Math.min(preferredHeight, openUp ? spaceAbove : spaceBelow) - margin);
        setPosition({
            left: Math.max(margin, rect.left),
            top: openUp ? Math.max(margin, rect.top - maxHeight - margin) : rect.bottom + margin,
            width: rect.width,
            maxHeight,
        });
    };

    useEffect(() => {
        const close = (event: MouseEvent) => {
            if (ref.current?.contains(event.target as Node) || menuRef.current?.contains(event.target as Node)) return;
            setOpen(false);
        };
        document.addEventListener("mousedown", close);
        return () => document.removeEventListener("mousedown", close);
    }, []);

    useEffect(() => {
        if (!open) return undefined;
        updatePosition();
        const reposition = () => updatePosition();
        window.addEventListener("resize", reposition);
        window.addEventListener("scroll", reposition, true);
        return () => {
            window.removeEventListener("resize", reposition);
            window.removeEventListener("scroll", reposition, true);
        };
    }, [open, options.length]);

    const menu = open ? (
        <div
            ref={menuRef}
            className="overflow-hidden rounded-xl border border-border bg-card text-card-foreground shadow-2xl"
            style={{
                position: "fixed",
                left: position.left,
                top: position.top,
                width: position.width,
                zIndex: 1000,
            }}
        >
            {searchable && (
                <div className="border-b border-border p-2">
                    <TextInput
                        icon={Search}
                        value={query}
                        onChange={(event: any) => setQuery(event.target.value)}
                        placeholder="Search..."
                        inputClassName="h-9 text-xs"
                        autoFocus
                    />
                </div>
            )}
            <div className="overflow-y-auto p-1" style={{ maxHeight: position.maxHeight }}>
                {filtered.length > 0 ? filtered.map((option) => {
                    const active = String(option.value) === String(value);
                    return (
                        <button
                            key={option.value}
                            type="button"
                            onClick={() => {
                                onChange(option.value, option);
                                setOpen(false);
                                setQuery("");
                            }}
                            className={cn(
                                "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-all cursor-pointer",
                                active ? "bg-primary/10 text-primary" : "hover:bg-secondary/70"
                            )}
                        >
                            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-secondary text-xs font-black uppercase text-muted-foreground">
                                {option.avatar || String(option.label || "?").charAt(0)}
                            </span>
                            <span className="min-w-0 flex-1">
                                <span className="block truncate text-xs font-bold text-foreground">{option.label}</span>
                                {option.description && <span className="block truncate text-[9px] font-bold uppercase tracking-widest text-muted-foreground">{option.description}</span>}
                            </span>
                            {active && <Check className="h-4 w-4 shrink-0" />}
                        </button>
                    );
                }) : (
                    <div className="px-3 py-8 text-center text-xs font-bold text-muted-foreground">No matches found.</div>
                )}
            </div>
        </div>
    ) : null;

    return (
        <div className={cn("relative w-full", className)} ref={ref}>
            <button
                ref={buttonRef}
                type="button"
                onClick={() => setOpen((next) => !next)}
                className={cn(
                    "flex h-11 w-full items-center gap-3 rounded-xl border border-border bg-input px-3 text-left text-xs font-bold text-foreground outline-none transition-all hover:border-primary/50 focus:border-primary focus:ring-4 focus:ring-primary/10 cursor-pointer",
                    !selected && "text-muted-foreground"
                )}
            >
                {Icon && <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />}
                <span className="min-w-0 flex-1 truncate">{selected?.label || placeholder}</span>
                <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200", open && "rotate-180")} />
            </button>

            {typeof document !== "undefined" && createPortal(menu, document.body)}
        </div>
    );
};
