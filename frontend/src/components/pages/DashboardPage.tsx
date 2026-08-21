import React from 'react';
import { AlertTriangle, Clock, Truck, MapPin, RefreshCw } from 'lucide-react';
import { Card, EmptyState, Spinner, Button } from '../ui';

interface DashboardPageProps {
    insights: any;
    loadingInsights: boolean;
    insightsError: string;
    fetchInsights: () => void;
}

export default function DashboardPage({
    insights,
    loadingInsights,
    insightsError,
    fetchInsights
}: DashboardPageProps) {
    if (loadingInsights && !insights) {
        return (
            <div className="h-[400px] flex flex-col items-center justify-center text-slate-500 gap-3">
                <Spinner className="h-8 w-8 text-emerald-500 animate-spin" />
                <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground animate-pulse">
                    Generating operational SLA alerts...
                </span>
            </div>
        );
    }

    if (insightsError) {
        return (
            <div className="p-6">
                <EmptyState
                    icon={AlertTriangle}
                    title="Operational Sync Failure"
                    description={insightsError}
                    action={
                        <Button onClick={fetchInsights} variant="outline" size="sm">
                            Retry Connection
                        </Button>
                    }
                />
            </div>
        );
    }

    if (!insights) {
        return (
            <div className="p-6 text-center text-slate-500">
                No insights loadable. Please make sure uvicorn is running.
            </div>
        );
    }

    return (
        <div className="space-y-6 pb-12 overflow-y-auto h-full px-2">
            {/* Dashboard Title Toolbar */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-black text-slate-800 flex items-center gap-2">
                        <ActivityIcon className="h-5 w-5 text-emerald-600" />
                        SLA Analytics & Proactive Signals
                    </h2>
                    <p className="text-xs text-slate-500">Snapshot time baseline: 2026-08-16 11:00 AM IST</p>
                </div>

                <button
                    onClick={fetchInsights}
                    disabled={loadingInsights}
                    className="flex items-center space-x-1.5 px-3 py-1.5 bg-white border border-border text-xs text-slate-650 hover:bg-slate-50 disabled:opacity-40 rounded-xl transition cursor-pointer shadow-sm"
                >
                    <RefreshCw className={`h-3.5 w-3.5 text-slate-500 ${loadingInsights ? 'animate-spin' : ''}`} />
                    <span className="font-bold">Sync</span>
                </button>
            </div>

            {/* Scorecards grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card className="p-5 flex items-center space-x-4 bg-white border border-border shadow-sm">
                    <div className="p-3 bg-red-50 rounded-xl border border-red-100 shrink-0">
                        <AlertTriangle className="h-6 w-6 text-red-500" />
                    </div>
                    <div>
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">SLA Breaches</span>
                        <span className="text-2xl font-black tracking-tight text-slate-800 font-mono">{insights.sla_breaches_count}</span>
                    </div>
                </Card>

                <Card className="p-5 flex items-center space-x-4 bg-white border border-border shadow-sm">
                    <div className="p-3 bg-amber-50 rounded-xl border border-amber-100 shrink-0">
                        <AlertTriangle className="h-6 w-6 text-amber-500" />
                    </div>
                    <div>
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">SLA Warnings</span>
                        <span className="text-2xl font-black tracking-tight text-slate-800 font-mono">{insights.sla_warnings_count}</span>
                    </div>
                </Card>

                <Card className="p-5 flex items-center space-x-4 bg-white border border-border shadow-sm">
                    <div className="p-3 bg-blue-50 rounded-xl border border-blue-100 shrink-0">
                        <Clock className="h-6 w-6 text-blue-500" />
                    </div>
                    <div>
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">Unassigned Tickets</span>
                        <span className="text-2xl font-black tracking-tight text-slate-800 font-mono">{insights.unassigned_tickets_count}</span>
                    </div>
                </Card>

                <Card className="p-5 flex items-center space-x-4 bg-white border border-border shadow-sm">
                    <div className="p-3 bg-purple-50 rounded-xl border border-purple-100 shrink-0">
                        <Truck className="h-6 w-6 text-purple-500" />
                    </div>
                    <div>
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">Delayed Pickups</span>
                        <span className="text-2xl font-black tracking-tight text-slate-800 font-mono">{insights.delayed_pickups_count}</span>
                    </div>
                </Card>
            </div>

            {/* Detailed reports */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* SLA Violations / Warning tickets */}
                <div className="bg-white border border-border rounded-2xl p-5 space-y-4 shadow-sm">
                    <h3 className="text-xs font-black text-slate-800 tracking-wider uppercase flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-red-500" />
                        Critically Breached / Warning Tickets
                    </h3>

                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs border-collapse">
                            <thead>
                                <tr className="border-b border-border text-slate-400 uppercase font-black text-[9px] tracking-wider">
                                    <th className="py-2.5 pb-3">Ticket</th>
                                    <th className="py-2.5 pb-3">Account</th>
                                    <th className="py-2.5 pb-3">Priority</th>
                                    <th className="py-2.5 pb-3 text-right font-mono">Elapsed / SLA Target</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {insights.sla_breaches?.map((t: any, i: number) => (
                                    <tr key={i} className="hover:bg-slate-50 text-slate-700 transition">
                                        <td className="py-3 font-bold text-slate-800 text-[13px]">
                                            {t.ticket_id}
                                            <span className="block font-medium text-[10.5px] text-slate-400 max-w-[200px] truncate mt-0.5">{t.subject}</span>
                                        </td>
                                        <td className="py-3 font-mono">{t.account_id}</td>
                                        <td className="py-3 font-bold text-red-650">{t.priority}</td>
                                        <td className="py-3 text-right font-mono text-red-600 font-black text-xs">
                                            {t.elapsed_minutes}m / {t.sla_target_minutes}m
                                        </td>
                                    </tr>
                                ))}
                                {insights.sla_warnings?.map((t: any, i: number) => (
                                    <tr key={i} className="hover:bg-slate-50 text-slate-700 transition">
                                        <td className="py-3 font-bold text-slate-800 text-[13px]">
                                            {t.ticket_id}
                                            <span className="block font-medium text-[10.5px] text-slate-400 max-w-[200px] truncate mt-0.5">{t.subject}</span>
                                        </td>
                                        <td className="py-3 font-mono">{t.account_id}</td>
                                        <td className="py-3 font-bold text-amber-600">{t.priority}</td>
                                        <td className="py-3 text-right font-mono text-amber-600 font-black text-xs">
                                            {t.elapsed_minutes}m / {t.sla_target_minutes}m
                                        </td>
                                    </tr>
                                ))}
                                {(insights.sla_breaches?.length === 0 && insights.sla_warnings?.length === 0) && (
                                    <tr>
                                        <td colSpan={4} className="py-8 text-center text-slate-400 font-bold">
                                            No active SLA violations detected. All tickets within SLA.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Delayed Pickups tracker */}
                <div className="bg-white border border-border rounded-2xl p-5 space-y-4 shadow-sm">
                    <h3 className="text-xs font-black text-slate-800 tracking-wider uppercase flex items-center gap-2">
                        <Truck className="h-4 w-4 text-purple-500" />
                        Delayed Shipment Pickups
                    </h3>

                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs border-collapse">
                            <thead>
                                <tr className="border-b border-border text-slate-400 uppercase font-black text-[9px] tracking-wider">
                                    <th className="py-2.5 pb-3">Order</th>
                                    <th className="py-2.5 pb-3">Account</th>
                                    <th className="py-2.5 pb-3">Carrier</th>
                                    <th className="py-2.5 pb-3 text-right font-mono">Delay Mins</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {insights.delayed_pickups?.map((o: any, i: number) => (
                                    <tr key={i} className="hover:bg-slate-50 text-slate-700 transition">
                                        <td className="py-3 font-bold text-slate-800 text-[13px]">
                                            {o.order_id}
                                            <span className="block text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-100 px-1.5 py-0.5 rounded w-max mt-0.5">
                                                {o.status}
                                            </span>
                                        </td>
                                        <td className="py-3 font-mono">{o.account_id}</td>
                                        <td className="py-3 font-semibold text-slate-705">{o.carrier}</td>
                                        <td className="py-3 text-right font-mono font-black text-amber-600 text-xs">{o.delay_minutes}m</td>
                                    </tr>
                                ))}
                                {insights.delayed_pickups?.length === 0 && (
                                    <tr>
                                        <td colSpan={4} className="py-8 text-center text-slate-400 font-bold">
                                            No delayed pick-ups found at baseline.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Carrier reliability scorecard */}
                {insights.carrier_scorecard && (
                    <div className="bg-white border border-border rounded-2xl p-5 space-y-4 shadow-sm col-span-1 lg:col-span-2">
                        <h3 className="text-xs font-black text-slate-800 tracking-wider uppercase flex items-center gap-2">
                            <MapPin className="h-4 w-4 text-emerald-600" />
                            Carrier Failure Scorecard (Tenant Aggregates)
                        </h3>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-1">
                            {Object.entries(insights.carrier_scorecard).map(([name, stats]: [string, any]) => {
                                const failureRatePercent = Math.round(stats.failure_rate * 100);
                                const isHighFailure = failureRatePercent >= 15;

                                return (
                                    <div key={name} className="p-4 bg-slate-50/50 border border-border rounded-xl space-y-2 shadow-sm">
                                        <span className="font-bold text-xs text-slate-805 block font-mono">{name}</span>
                                        <div className="flex items-baseline justify-between pt-1">
                                            <span className="text-[10px] text-slate-400 block font-bold">Failure Rate</span>
                                            <span className={`text-sm font-black font-mono ${isHighFailure ? 'text-red-500' : 'text-emerald-705'}`}>
                                                {failureRatePercent}%
                                            </span>
                                        </div>
                                        <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                                            <div
                                                className={`h-full ${isHighFailure ? 'bg-red-500' : 'bg-emerald-500'}`}
                                                style={{ width: `${Math.min(100, Math.max(8, failureRatePercent))}%` }}
                                            ></div>
                                        </div>
                                        <span className="text-[9px] font-bold text-slate-400 block text-right pt-0.5">
                                            {stats.carrier_faults} faults in {stats.total_orders} orders
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

function ActivityIcon(props: React.SVGProps<SVGSVGElement>) {
    return (
        <svg
            {...props}
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
        </svg>
    );
}
