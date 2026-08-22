import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
    User as UserIcon,
    LogOut,
    ChevronLeft,
    ChevronRight,
    PlusCircle,
    Trash2,
    FileText,
    LayoutDashboard,
    MessageSquare
} from 'lucide-react';
import DocumentViewer from '../chat/DocumentViewer';
import parcelPilotLogo from '../../assets/parcelpilot.png';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface UserProfile {
    user_id: string;
    email: string;
    role: string;
    account_id: string | null;
    full_name: string;
}

interface SessionItem {
    id: string;
    user_id: string;
    title: string;
    created_at: string;
    updated_at: string;
}

interface MainLayoutProps {
    children: React.ReactNode;
    user: UserProfile | null;
    token: string | null;
    handleLogout: () => void;
    sessions: SessionItem[];
    loadingSessions: boolean;
    deleteSession: (sessionId: string, e: React.MouseEvent) => void;
    showDocViewer: boolean;
    setShowDocViewer: (show: boolean) => void;
}

function ParcelPilotLogo({ className = "h-5 w-5" }: { className?: string }) {
    return (
        <img src={parcelPilotLogo} alt="ParcelPilot AI Logo" className={className} />
    );
}

export default function MainLayout({
    children,
    user,
    token,
    handleLogout,
    sessions,
    loadingSessions,
    deleteSession,
    showDocViewer,
    setShowDocViewer
}: MainLayoutProps) {
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const navigate = useNavigate();
    const location = useLocation();

    const isChatRoute = location.pathname.startsWith('/chat');
    const isDashboardRoute = location.pathname.startsWith('/dashboard');

    return (
        <div className="fixed inset-0 flex h-screen w-screen overflow-hidden bg-slate-50 text-slate-800 font-sans z-10">
            {/* Collapsible Left Sidebar */}
            <aside
                className={`${sidebarCollapsed ? 'w-0 border-r-0' : 'w-80'
                    } bg-white border-r border-border flex flex-col h-full shrink-0 z-20 transition-all duration-300 relative overflow-hidden`}
            >
                {/* Sidebar Header */}
                <div className="p-5 border-b border-border flex items-center space-x-3 bg-white">
                    <ParcelPilotLogo className="w-10 h-10 shadow-sm rounded-full shrink-0 bg-white p-0.5 object-contain" />
                    <div>
                        <h1 className="font-extrabold text-sm tracking-tight text-slate-800 leading-none">ParcelPilot AI</h1>
                        <span className="text-[9px] font-black text-emerald-650 uppercase tracking-widest block mt-0.5">
                            Support Center
                        </span>
                    </div>
                </div>

                {/* Sidebar scroll content */}
                <div className="flex-1 overflow-y-auto p-4 space-y-6">
                    {/* Plus New Chat Button */}
                    <button
                        onClick={() => navigate('/chat')}
                        className="w-full flex items-center justify-center gap-2 border border-emerald-500/25 hover:border-emerald-500/60 bg-emerald-50/20 hover:bg-emerald-50/50 text-emerald-700 p-2.5 rounded-xl text-xs font-black uppercase tracking-wider transition cursor-pointer"
                    >
                        <PlusCircle className="h-4.5 w-4.5 text-emerald-600" />
                        <span>New Assistance Chat</span>
                    </button>

                    {/* Navigation routes for internal managers */}
                    {user && user.role !== 'customer' && (
                        <div className="space-y-1.5">
                            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block pl-2 mb-2">Navigation</span>
                            <button
                                onClick={() => navigate('/chat')}
                                className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer text-left ${isChatRoute ? 'bg-emerald-50/70 text-emerald-800 border border-emerald-100' : 'text-slate-600 hover:bg-slate-100/70'
                                    }`}
                            >
                                <MessageSquare className="h-4 w-4 text-slate-450" />
                                AI Agent Console
                            </button>
                            <button
                                onClick={() => navigate('/dashboard')}
                                className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer text-left ${isDashboardRoute ? 'bg-emerald-50/70 text-emerald-800 border border-emerald-100' : 'text-slate-600 hover:bg-slate-100/70'
                                    }`}
                            >
                                <LayoutDashboard className="h-4 w-4 text-slate-450" />
                                Operations Dashboard
                            </button>
                        </div>
                    )}

                    {/* History Chat Sessions List */}
                    <div className="space-y-2">
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block pl-2">Recent Sessions</span>
                        <div className="space-y-1 overflow-y-auto max-h-[280px] pr-1">
                            {sessions.map((s) => {
                                const isActive = location.pathname === `/chat/${s.id}`;
                                return (
                                    <div
                                        key={s.id}
                                        onClick={() => navigate(`/chat/${s.id}`)}
                                        className={`w-full flex items-center justify-between p-2.5 rounded-xl text-xs font-bold transition cursor-pointer text-left select-none relative group ${isActive ? 'bg-slate-50 border border-border text-slate-800' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                                            }`}
                                    >
                                        <div className="flex items-center space-x-2 truncate pr-2">
                                            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${isActive ? 'bg-emerald-500' : 'bg-slate-300'}`}></span>
                                            <span className="truncate">{s.title}</span>
                                        </div>
                                        <button
                                            onClick={(e) => deleteSession(s.id, e)}
                                            className="opacity-0 group-hover:opacity-100 hover:text-red-500 cursor-pointer p-0.5 shrink-0 transition"
                                        >
                                            <Trash2 className="h-3.5 w-3.5" />
                                        </button>
                                    </div>
                                );
                            })}
                            {!loadingSessions && sessions.length === 0 && (
                                <div className="pl-2.5 text-[11px] font-semibold text-slate-400 italic">No chat history.</div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Sidebar User Footer */}
                {user && (
                    <div className="p-4 border-t border-border bg-white flex flex-col gap-3 shrink-0">
                        <div className="flex items-center space-x-3 w-full">
                            <div className="w-9 h-9 rounded-xl bg-slate-50 border border-border flex items-center justify-center shrink-0">
                                <UserIcon className="h-4.5 w-4.5 text-slate-400" />
                            </div>
                            <div className="min-w-0 flex-1">
                                <span className="font-extrabold text-xs text-slate-800 block truncate">{user.full_name}</span>
                                <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider block">
                                    {user.role} {user.account_id ? `• ${user.account_id}` : '• Global Scope'}
                                </span>
                            </div>
                        </div>

                        <button
                            onClick={handleLogout}
                            className="w-full flex items-center justify-start text-xs font-bold text-slate-500 hover:text-rose-600 hover:bg-rose-50/50 border border-border h-10 px-3 rounded-xl transition cursor-pointer"
                        >
                            <LogOut className="h-3.5 w-3.5 mr-2" />
                            <span>Sign Out</span>
                        </button>
                    </div>
                )}
            </aside>

            {/* Main Content Pane Viewport */}
            <main className="flex-1 flex flex-col h-full overflow-hidden bg-slate-50 relative">
                {/* Header Navbar */}
                <header className="h-16 border-b border-border bg-white flex items-center justify-between px-6 z-10 shrink-0">
                    <div className="flex items-center">
                        {/* Collapsible toggle chevron */}
                        <button
                            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
                            className="p-1.5 border border-border bg-white rounded-lg hover:bg-slate-50 transition cursor-pointer text-slate-400 shadow-sm mr-4"
                            title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                        >
                            {sidebarCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
                        </button>

                        <h2 className="text-xs font-black text-slate-800 tracking-wider uppercase">
                            {user?.role === 'customer'
                                ? 'Customer Support Chatbot'
                                : isDashboardRoute
                                    ? 'Operations Dashboard'
                                    : 'Agent AI Orchestrator'}
                        </h2>
                    </div>

                    <div className="flex items-center space-x-3">
                        {isChatRoute && (
                            <button
                                onClick={() => setShowDocViewer(!showDocViewer)}
                                className={`flex items-center gap-1.5 px-3 py-1.5 border border-border text-xs font-bold rounded-xl shadow-sm transition hover:bg-slate-50 cursor-pointer ${showDocViewer ? 'bg-emerald-50 border-emerald-300 text-emerald-800 hover:bg-emerald-50' : 'bg-white text-slate-600'
                                    }`}
                            >
                                <FileText className="h-3.5 w-3.5" />
                                <span>Policy Vault</span>
                            </button>
                        )}
                    </div>
                </header>

                {/* Workspace body panels */}
                <div className="flex-1 overflow-hidden p-6 flex gap-6">
                    <div className="flex-1 flex gap-6 overflow-hidden h-full">
                        {children}

                        {/* Right side splitpane: Document Previews/Uploads library */}
                        {isChatRoute && showDocViewer && (
                            <DocumentViewer
                                API_URL={API_URL}
                                token={token}
                                user={user}
                                onClose={() => setShowDocViewer(false)}
                            />
                        )}
                    </div>
                </div>
            </main>
        </div>
    );
}
