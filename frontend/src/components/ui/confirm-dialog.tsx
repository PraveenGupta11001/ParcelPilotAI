import { AlertTriangle } from "lucide-react";
import { Button } from "./button";
import { Modal } from "./modal";

interface ConfirmDialogProps {
    open: boolean;
    onClose: () => void;
    onConfirm: () => void;
    title: string;
    description: string;
    confirmLabel?: string;
    cancelLabel?: string;
    variant?: "primary" | "secondary" | "danger" | "success" | "outline";
    loading?: boolean;
}

export const ConfirmDialog = ({
    open,
    onClose,
    onConfirm,
    title,
    description,
    confirmLabel = "Confirm",
    cancelLabel = "Cancel",
    variant = "danger",
    loading = false,
}: ConfirmDialogProps) => (
    <Modal
        open={open}
        onClose={onClose}
        title={title}
        description={description}
        icon={AlertTriangle}
        className="max-w-md bg-white border border-border"
        disableClose={loading}
    >
        <div className="flex gap-3 pt-2">
            <Button
                type="button"
                variant="secondary"
                className="flex-1 text-xs"
                onClick={onClose}
                disabled={loading}
            >
                {cancelLabel}
            </Button>
            <Button
                type="button"
                variant={variant}
                className="flex-1 text-xs text-white bg-slate-900 border-none"
                onClick={onConfirm}
                disabled={loading}
            >
                {loading ? "Working..." : confirmLabel}
            </Button>
        </div>
    </Modal>
);
