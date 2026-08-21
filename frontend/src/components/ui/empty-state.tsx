import { Card } from "./card";

export const EmptyState = ({ icon: Icon, title, description, action }: { icon?: any; title: string; description?: string; action?: any }) => (
    <Card className="flex flex-col items-center justify-center border-dashed bg-card/70 p-12 text-center">
        {Icon && (
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-secondary text-muted-foreground">
                <Icon className="h-7 w-7" />
            </div>
        )}
        <h3 className="text-lg font-black">{title}</h3>
        {description && <p className="mt-2 max-w-md text-sm font-medium text-muted-foreground">{description}</p>}
        {action && <div className="mt-6">{action}</div>}
    </Card>
);
