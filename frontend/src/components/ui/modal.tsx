import { X } from "lucide-react";
import { cn } from "../../lib/utils";
import { Card } from "./card";

interface ModalProps {
    open: boolean;
    onClose: () => void;
    title: string;
    description?: string;
    icon?: any;
    children: any;
    className?: string;
    disableClose?: boolean;
    zIndex?: string;
}

export const Modal = ({
    open,
    onClose,
    title,
    description,
    icon,
    children,
    className,
    disableClose = false,
    zIndex = "z-[900]"
}: ModalProps) => {
    if (!open) return null;
    const Icon = icon;

    return (
        <div className={cn("fixed inset-0 flex items-center justify-center p-4", zIndex)}>
            <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-md" onClick={disableClose ? undefined : onClose} />
            <Card className={cn("relative max-h-[92vh] w-full max-w-lg overflow-y-auto p-6 shadow-2xl animate-in zoom-in-95 duration-200 bg-white z-10", className)}>
                <div className="mb-6 flex items-start justify-between gap-4">
                    <div className="flex-1">
                        <h2 className="text-2xl font-black tracking-tight">{title}</h2>
                        {description && <p className="mt-1 text-sm font-medium text-slate-500">{description}</p>}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                        {Icon && (
                            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-650">
                                <Icon className="h-5 w-5" />
                            </div>
                        )}
                        {!disableClose && (
                            <button
                                type="button"
                                onClick={onClose}
                                className="rounded-xl p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors cursor-pointer"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        )}
                    </div>
                </div>
                {children}
            </Card>
        </div>
    );
};
