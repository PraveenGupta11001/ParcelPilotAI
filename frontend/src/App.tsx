import React, { useState, useEffect, useRef } from 'react';
import {
  Shield,
  Send,
  AlertTriangle,
  Clock,
  FileText,
  RefreshCw,
  User as UserIcon,
  LogOut,
  Truck,
  Activity,
  ChevronDown,
  ChevronUp,
  MapPin
} from 'lucide-react';
import { Button, Card, EmptyState, TextInput, Select, Spinner } from './components/ui';

// API Server Endpoint (FastAPI runs on port 8000 by default)
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface UserProfile {
  user_id: string;
  email: string;
  role: string;
  account_id: string | null;
  full_name: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  tool_calls?: any[];
}

export default function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [user, setUser] = useState<UserProfile | null>(
    localStorage.getItem('user') ? JSON.parse(localStorage.getItem('user')!) : null
  );

  // Login Form State
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');

  // Chat State
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loadingChat, setLoadingChat] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Dashboard Insights State
  const [insights, setInsights] = useState<any>(null);
  const [loadingInsights, setLoadingInsights] = useState(false);
  const [insightsError, setInsightsError] = useState('');

  // Expandable trace states
  const [expandedTrace, setExpandedTrace] = useState<Record<string, boolean>>({});
  const [expandedSection, setExpandedSection] = useState<Record<string, boolean>>({});

  // Active view tab for internal roles (chat vs dashboard)
  const [activeTab, setActiveTab] = useState<'chat' | 'dashboard'>('chat');

  // Auto-scroll chat
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loadingChat]);

  // Fetch Dashboard Insights if internal role
  useEffect(() => {
    if (token && user && user.role !== 'customer') {
      fetchInsights();
    }
  }, [token, user]);

  const fetchInsights = async () => {
    setLoadingInsights(true);
    setInsightsError('');
    try {
      const res = await fetch(`${API_URL}/insights`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        setInsights(data);
      } else {
        const err = await res.json();
        setInsightsError(err.detail || 'Failed to fetch insights');
      }
    } catch (e) {
      setInsightsError('Database backend unreachable. Make sure uvicorn is running.');
    } finally {
      setLoadingInsights(false);
    }
  };

  const handleLogin = async (e?: React.FormEvent, customUser?: any) => {
    if (e) e.preventDefault();
    setLoginError('');

    const loginEmail = customUser ? customUser.email : email;
    const loginPassword = customUser ? customUser.password : password;

    try {
      const res = await fetch(`${API_URL}/auth/mock-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail, password: loginPassword })
      });
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('user', JSON.stringify(data.user));
        setToken(data.access_token);
        setUser(data.user);
        setMessages([]); // Clear history on role transition
        setActiveTab(data.user.role === 'customer' ? 'chat' : 'chat');
      } else {
        const err = await res.json();
        setLoginError(err.detail || 'Login failed.');
      }
    } catch (err) {
      setLoginError('Backend connection error. Make sure FastAPI server is running.');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
    setMessages([]);
    setInsights(null);
  };

  const handleRoleSwap = (user_id: string) => {
    const roles: Record<string, any> = {
      'cust-northstar': { email: 'northstar@parcelpilot.ai', password: 'password123' },
      'cust-lumenworks': { email: 'lumenworks@parcelpilot.ai', password: 'password123' },
      'cust-beacon': { email: 'beacon@parcelpilot.ai', password: 'password123' },
      'agent-maya': { email: 'maya@parcelpilot.ai', password: 'password123' },
      'lead-rohit': { email: 'rohit@parcelpilot.ai', password: 'password123' }
    };
    handleLogin(undefined, roles[user_id]);
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || loadingChat) return;

    const userMsg: Message = {
      id: Math.random().toString(),
      role: 'user',
      content: inputMessage
    };

    setMessages(prev => [...prev, userMsg]);
    setInputMessage('');
    setLoadingChat(true);

    try {
      // Package clean message history
      const formattedHistory = messages.map(m => ({
        role: m.role,
        content: m.content
      }));

      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message: userMsg.content,
          chat_history: formattedHistory
        })
      });

      if (res.ok) {
        const data = await res.json();
        const assistantMsg: Message = {
          id: Math.random().toString(),
          role: 'assistant',
          content: data.text_response,
          tool_calls: data.tool_calls
        };
        setMessages(prev => [...prev, assistantMsg]);

        // Refresh insights if internal
        if (user && user.role !== 'customer') {
          fetchInsights();
        }
      } else {
        setMessages(prev => [...prev, {
          id: Math.random().toString(),
          role: 'assistant',
          content: 'Error: Failed to process query through the backend orchestrator.'
        }]);
      }
    } catch (e) {
      setMessages(prev => [...prev, {
        id: Math.random().toString(),
        role: 'assistant',
        content: 'Error: API server unreachable.'
      }]);
    } finally {
      setLoadingChat(false);
    }
  };

  const handleConfirmAction = async (proposalId: number, msgId: string) => {
    try {
      const res = await fetch(`${API_URL}/chat/confirm`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ proposal_id: proposalId })
      });

      if (res.ok) {
        const data = await res.json();

        // Replace message content or add a follow-up alert
        setMessages(prev => prev.map(m => {
          if (m.id === msgId && m.tool_calls) {
            // Update the state of proposal within tool call response
            const updatedTools = m.tool_calls.map(tc => {
              if (tc.tool_name === 'propose_action') {
                const parsed = JSON.parse(tc.output);
                if (parsed.proposal_id === proposalId) {
                  parsed.status = 'APPROVED';
                  return { ...tc, output: JSON.stringify(parsed) };
                }
              }
              return tc;
            });
            return {
              ...m,
              content: m.content + `\n\n✅ **Action Confirmed!** ${data.message}`,
              tool_calls: updatedTools
            };
          }
          return m;
        }));

        if (user && user.role !== 'customer') {
          fetchInsights();
        }
      } else {
        const err = await res.json();
        alert(`Failed to confirm proposal: ${err.detail}`);
      }
    } catch (e) {
      alert('Internal connection error during confirmation stage.');
    }
  };

  if (!token || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 font-sans text-foreground">
        <div className="w-full max-w-md glass-card p-8 border border-border shadow-2xl relative z-10">
          <div className="flex justify-center mb-6">
            <div className="p-3.5 bg-primary/10 rounded-xl border border-primary/20 flex items-center justify-center">
              <Shield className="h-7 w-7 text-primary" />
            </div>
          </div>
          <h2 className="text-2xl font-black text-center tracking-tight mb-1 text-white">ParcelPilot Support</h2>
          <p className="text-xs text-muted-foreground font-medium text-center mb-8">
            Access secure chatbot interface & analytics
          </p>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-[10px] font-black text-muted-foreground uppercase tracking-widest mb-2">Email Address</label>
              <TextInput
                type="email"
                value={email}
                onChange={(e: any) => setEmail(e.target.value)}
                inputClassName="text-xs font-bold"
                placeholder="eg: maya@parcelpilot.ai"
                required
              />
            </div>
            <div>
              <label className="block text-[10px] font-black text-muted-foreground uppercase tracking-widest mb-2">Password</label>
              <TextInput
                type="password"
                value={password}
                onChange={(e: any) => setPassword(e.target.value)}
                inputClassName="text-xs font-bold"
                placeholder="••••••••"
                required
              />
            </div>

            {loginError && (
              <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 p-3 rounded-xl font-bold">
                {loginError}
              </div>
            )}

            <Button
              type="submit"
              variant="primary"
              className="w-full text-xs font-black uppercase tracking-widest"
            >
              Sign In
            </Button>
          </form>

          <div className="mt-8 border-t border-border pt-6">
            <p className="text-[10px] font-black text-muted-foreground uppercase tracking-widest mb-4 text-center">
              Quick Role Switcher Seeding
            </p>
            <div className="grid grid-cols-2 gap-3 text-[11px]">
              <button
                onClick={() => handleRoleSwap('cust-northstar')}
                className="p-3 border border-border hover:border-accent/40 rounded-xl bg-secondary/35 hover:bg-secondary text-left transition cursor-pointer"
              >
                <div className="font-bold text-foreground flex items-center gap-1">💼 <span>Northstar Cust</span></div>
                <span className="block text-[9px] text-muted-foreground font-bold mt-1 uppercase tracking-wider">ACCT-001 Enterprise</span>
              </button>
              <button
                onClick={() => handleRoleSwap('cust-lumenworks')}
                className="p-3 border border-border hover:border-accent/40 rounded-xl bg-secondary/35 hover:bg-secondary text-left transition cursor-pointer"
              >
                <div className="font-bold text-foreground flex items-center gap-1">⚡ <span>LumenWorks Cust</span></div>
                <span className="block text-[9px] text-muted-foreground font-bold mt-1 uppercase tracking-wider">ACCT-002 Growth</span>
              </button>
              <button
                onClick={() => handleRoleSwap('cust-beacon')}
                className="p-3 border border-border hover:border-accent/40 rounded-xl bg-secondary/35 hover:bg-secondary text-left transition cursor-pointer"
              >
                <div className="font-bold text-foreground flex items-center gap-1">🛍️ <span>Beacon Cust</span></div>
                <span className="block text-[9px] text-muted-foreground font-bold mt-1 uppercase tracking-wider">ACCT-003 Standard</span>
              </button>
              <button
                onClick={() => handleRoleSwap('agent-maya')}
                className="p-3 border border-border hover:border-accent/40 rounded-xl bg-secondary/35 hover:bg-secondary text-left transition cursor-pointer"
              >
                <div className="font-bold text-foreground flex items-center gap-1">🙋 <span>Maya Agent</span></div>
                <span className="block text-[9px] text-muted-foreground font-bold mt-1 uppercase tracking-wider">Internal Ops</span>
              </button>
              <button
                onClick={() => handleRoleSwap('lead-rohit')}
                className="p-3 border border-border hover:border-accent/40 rounded-xl bg-secondary/35 hover:bg-secondary text-left transition col-span-2 cursor-pointer"
              >
                <div className="font-bold text-foreground flex items-center gap-1">👑 <span>Rohit Lead</span></div>
                <span className="block text-[9px] text-muted-foreground font-bold mt-1 uppercase tracking-wider">Internal Operations Team Lead</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 flex h-screen w-screen overflow-hidden bg-background text-foreground font-sans z-10">
      {/* ChatGPT-style Left Sidebar */}
      <aside className="w-80 bg-slate-50/90 border-r border-border flex flex-col h-full shrink-0 z-20">
        {/* Sidebar Header */}
        <div className="p-5 border-b border-border flex items-center space-x-3 bg-white">
          <div className="w-8 h-8 rounded bg-primary flex items-center justify-center shadow shadow-primary/20">
            <Shield className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="font-black text-sm tracking-tight text-slate-800 leading-none">ParcelPilot AI</h1>
            <span className="text-[9px] font-black text-primary uppercase tracking-wider block mt-1">
              Support Center
            </span>
          </div>
        </div>

        {/* Sidebar Navigation & Chat Sessions */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {/* Active Workspaces / Tab Router for Admin/Maya/Rohit */}
          {user.role !== 'customer' && (
            <div className="space-y-2">
              <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block pl-2">Navigation</span>
              <div className="space-y-1">
                <button
                  onClick={() => setActiveTab('chat')}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer text-left ${activeTab === 'chat' ? 'bg-primary/10 text-primary' : 'text-slate-600 hover:bg-slate-200/60 hover:text-slate-900'}`}
                >
                  💬 AI Agent Console
                </button>
                <button
                  onClick={() => setActiveTab('dashboard')}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer text-left ${activeTab === 'dashboard' ? 'bg-primary/10 text-primary' : 'text-slate-600 hover:bg-slate-200/60 hover:text-slate-900'}`}
                >
                  📊 Operations Dashboard
                </button>
              </div>
            </div>
          )}

          {/* Quick Swap Sandbox Selector */}
          <div className="space-y-2">
            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block pl-2">Privilege Simulator</span>
            <div className="px-2">
              <Select
                value={user.user_id}
                onChange={(value: string) => handleRoleSwap(value)}
                options={[
                  { value: 'cust-northstar', label: 'Northstar (Customer)' },
                  { value: 'cust-lumenworks', label: 'LumenWorks (Customer)' },
                  { value: 'cust-beacon', label: 'Beacon Retail (Customer)' },
                  { value: 'agent-maya', label: 'Maya (Support Agent)' },
                  { value: 'lead-rohit', label: 'Rohit (Team Lead)' }
                ]}
                className="text-xs font-bold"
              />
            </div>
          </div>

          {/* Simulating Chat History / Recents (ChatGPT look) */}
          <div className="space-y-2">
            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block pl-2">Recent Sessions</span>
            <div className="space-y-1 pl-1">
              <div className="px-3 py-2 rounded-lg text-[11px] font-bold text-slate-600 hover:text-slate-800 transition flex items-center gap-2 cursor-pointer">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                <span>Active Session #S-829A</span>
              </div>
              <div className="px-3 py-2 rounded-lg text-[11px] font-bold text-slate-400 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-300"></span>
                <span>Audit Trail Logs</span>
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar Footer - User at the End */}
        <div className="p-4 border-t border-border bg-white flex flex-col gap-3">
          <div className="flex items-center space-x-3 w-full">
            <div className="w-9 h-9 rounded-xl bg-slate-100 border border-border flex items-center justify-center shrink-0">
              <UserIcon className="h-4.5 w-4.5 text-slate-500" />
            </div>
            <div className="min-w-0 flex-1">
              <span className="font-black text-xs text-slate-850 block truncate">{user.full_name}</span>
              <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider block">
                {user.role} {user.account_id ? `• ${user.account_id}` : '• Global Scope'}
              </span>
            </div>
          </div>

          <Button
            onClick={handleLogout}
            variant="ghost"
            className="w-full justify-start text-xs font-bold text-slate-500 hover:text-rose-600 hover:bg-rose-50/50 border border-border h-10 rounded-xl"
          >
            <LogOut className="h-3.5 w-3.5 mr-2" />
            <span>Sign Out</span>
          </Button>
        </div>
      </aside>

      {/* Main Screen Panel Viewport */}
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-[#fafbfd]">
        {/* Top active tab indicator name header */}
        <header className="h-16 border-b border-border bg-white flex items-center justify-between px-6 z-10 shrink-0">
          <div>
            <h2 className="text-xs font-black text-slate-800 tracking-wider uppercase">
              {user.role === 'customer' ? 'Customer Support chatbot' : activeTab === 'chat' ? 'Agent AI orchestrator' : 'Operations Dashboard'}
            </h2>
          </div>
          <div className="flex items-center space-x-2 text-[10px] font-bold uppercase tracking-widest text-slate-400">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>Live Security Scoping Active</span>
          </div>
        </header>

        {/* Workspace Body container */}
        <div className="flex-1 overflow-hidden p-6 flex gap-6">
          {/* Main workspace widgets */}
          {user.role !== 'customer' ? (
            activeTab === 'chat' ? (
              <div className="flex-1 flex gap-6 overflow-hidden">
                {renderChatPanel()}
              </div>
            ) : (
              <div className="flex-1 overflow-hidden">
                {renderDashboardPanel()}
              </div>
            )
          ) : (
            <div className="flex-1 flex gap-6 overflow-hidden">
              {renderChatPanel()}
            </div>
          )}
        </div>
      </main>
    </div>
  );

  function renderChatPanel() {
    return (
      <div className="flex-1 flex flex-col bg-white border border-border rounded-2xl overflow-hidden shadow-sm">
        {/* Messages Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="h-full flex items-center justify-center py-16">
              <EmptyState
                icon={Shield}
                title="ParcelPilot AI Copilot"
                description="Secure agent console initialized. Ask questions about shipments, policies, or initiate transactional proposals."
              />
            </div>
          )}

          {messages.map((m) => {
            const hasConfirmations = m.tool_calls?.some(tc => tc.tool_name === 'propose_action');
            const hasCitations = m.tool_calls?.some(tc => tc.tool_name === 'search_documents');
            const hasTrace = m.tool_calls && m.tool_calls.length > 0;

            return (
              <div
                key={m.id}
                className={`flex flex-col max-w-[85%] ${m.role === 'user' ? 'ml-auto items-end' : 'mr-auto items-start'}`}
              >
                <div
                  className={`px-4 py-3.5 rounded-2xl text-base leading-relaxed ${m.role === 'user'
                    ? 'bg-primary text-white font-bold rounded-tr-none'
                    : 'bg-slate-50 border border-border text-slate-800 rounded-tl-none shadow-sm'
                    }`}
                >
                  {/* Handle line breaks/paragraphs */}
                  {m.content.split('\n').map((para, i) => (
                    <p key={i} className={para.trim() ? "mb-2 last:mb-0" : "h-2"} style={{ wordBreak: 'break-word' }}>
                      {para}
                    </p>
                  ))}
                </div>

                {/* CITATIONS AND TRACES ATTACHED ONLY FOR ASSISTANT RESPONSE */}
                {m.role === 'assistant' && (
                  <div className="w-full mt-2 space-y-2">
                    {/* Render tool confirmations proposal cards if proposed */}
                    {hasConfirmations && m.tool_calls?.map((tc, idx) => {
                      if (tc.tool_name === 'propose_action') {
                        const parsed = JSON.parse(tc.output);
                        if (parsed.error) return null;

                        const isPending = parsed.status === 'PENDING';
                        const isApproved = parsed.status === 'APPROVED';

                        return (
                          <div key={idx} className="p-4 border border-border bg-slate-50 rounded-xl space-y-3">
                            <div className="flex items-center justify-between">
                              <span className="text-xs text-amber-600 font-bold uppercase tracking-wider block">
                                Proposed: {parsed.action_type}
                              </span>
                              <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${isApproved ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-amber-50 text-amber-700 border border-amber-200'
                                }`}>
                                {parsed.status}
                              </span>
                            </div>

                            <table className="w-full text-xs text-slate-650 border-collapse">
                              <tbody>
                                <tr>
                                  <td className="py-1 font-semibold text-slate-500">Proposal ID</td>
                                  <td className="py-1 text-slate-900 font-bold">#{parsed.proposal_id}</td>
                                </tr>
                                {parsed.order_id && (
                                  <tr>
                                    <td className="py-1 font-semibold text-slate-500">Order ID</td>
                                    <td className="py-1 text-slate-900 font-bold font-mono">{parsed.order_id}</td>
                                  </tr>
                                )}
                                {parsed.ticket_id && (
                                  <tr>
                                    <td className="py-1 font-semibold text-slate-500">Ticket ID</td>
                                    <td className="py-1 text-slate-900 font-bold">{parsed.ticket_id}</td>
                                  </tr>
                                )}
                                {parsed.amount !== null && (
                                  <tr>
                                    <td className="py-1 font-semibold text-slate-500">Amount</td>
                                    <td className="py-1 text-emerald-700 font-black text-xs font-mono">INR {parsed.amount}</td>
                                  </tr>
                                )}
                                <tr>
                                  <td className="py-1 font-semibold text-slate-500">Reason</td>
                                  <td className="py-1 text-slate-700">{parsed.reason}</td>
                                </tr>
                              </tbody>
                            </table>

                            {isPending && (
                              <div className="flex gap-2 pt-2">
                                <button
                                  onClick={() => handleConfirmAction(parsed.proposal_id, m.id)}
                                  className="flex-1 py-1.5 bg-primary text-white font-bold text-xs rounded hover:bg-primary/90 transition-colors cursor-pointer"
                                >
                                  Confirm Action
                                </button>
                                <button
                                  onClick={() => {
                                    alert('Proposal rejected locally.');
                                  }}
                                  className="px-3 py-1.5 bg-white border border-border text-slate-600 hover:text-slate-900 text-xs rounded transition-colors cursor-pointer"
                                >
                                  Reject
                                </button>
                              </div>
                            )}
                          </div>
                        );
                      }
                      return null;
                    })}

                    {/* Expandable Source citations preview tool */}
                    {hasCitations && m.tool_calls?.map((tc, idx) => {
                      if (tc.tool_name === 'search_documents') {
                        const parsed = JSON.parse(tc.output);
                        if (parsed.error || !parsed.length) return null;

                        const idKey = `${m.id}-citations`;

                        return (
                          <div key={idx} className="text-xs">
                            <button
                              onClick={() => setExpandedSection(prev => ({ ...prev, [idKey]: !prev[idKey] }))}
                              className="flex items-center space-x-1.5 text-slate-500 hover:text-slate-800 font-medium py-1 transition-colors"
                            >
                              <FileText className="h-3 w-3" />
                              <span>{expandedSection[idKey] ? 'Hide' : 'Show'} Document Citations ({parsed.length})</span>
                              {expandedSection[idKey] ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                            </button>

                            {expandedSection[idKey] && (
                              <div className="mt-1 space-y-2 border-l-2 border-border pl-3 pt-1">
                                {parsed.map((c: any, cIdx: number) => (
                                  <div key={cIdx} className="bg-white p-2.5 rounded-lg border border-border shadow-sm">
                                    <div className="flex items-center justify-between mb-1.5">
                                      <span className="font-bold text-slate-800 block">{c.document_name} [Page index: {c.chunk_index}]</span>
                                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${c.authority_level === 1 ? 'bg-red-50 text-red-700 font-bold border border-red-200' : c.authority_level === 2 ? 'bg-amber-50 text-amber-700 border border-amber-20 border-amber-200' : 'bg-slate-100 text-slate-650'
                                        }`}>
                                        SLA Authority: Lvl {c.authority_level}
                                      </span>
                                    </div>
                                    <p className="text-slate-600 italic text-[11px] leading-relaxed">
                                      "{c.content.length > 200 ? c.content.substring(0, 200) + '...' : c.content}"
                                    </p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      }
                      return null;
                    })}

                    {/* Expandable Tool calling traces debug panel */}
                    {hasTrace && (
                      <div className="text-xs">
                        <button
                          onClick={() => setExpandedTrace(prev => ({ ...prev, [m.id]: !prev[m.id] }))}
                          className="flex items-center space-x-1.5 text-slate-500 hover:text-slate-850 font-medium py-1 transition-colors"
                        >
                          <Activity className="h-3 w-3" />
                          <span>{expandedTrace[m.id] ? 'Hide' : 'Show'} Trace logs ({m.tool_calls!.length})</span>
                          {expandedTrace[m.id] ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                        </button>

                        {expandedTrace[m.id] && (
                          <div className="mt-1 bg-slate-50 rounded-xl border border-border p-3 space-y-3 font-mono text-[10px] text-slate-600">
                            {m.tool_calls!.map((tc, tcIdx) => (
                              <div key={tcIdx} className="space-y-1">
                                <div className="text-emerald-700 font-bold">🔧 {tc.tool_name}()</div>
                                <div className="pl-3 text-slate-500">INPUT: {JSON.stringify(tc.args)}</div>
                                <div className="pl-3 text-slate-700">
                                  OUTPUT: {tc.output.length > 250 ? tc.output.substring(0, 250) + '...' : tc.output}
                                </div>
                                {tcIdx < m.tool_calls!.length - 1 && <div className="border-t border-border/50 my-2"></div>}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {loadingChat && (
            <div className="flex items-center space-x-2 text-xs text-slate-600 font-semibold pl-4 py-2">
              <RefreshCw className="h-3.5 w-3.5 animate-spin text-primary" />
              <span>AI Agent reasoning & searching database...</span>
            </div>
          )}
          <div ref={scrollRef}></div>
        </div>

        {/* Input panel footer */}
        <form onSubmit={handleSendMessage} className="p-4 border-t border-border bg-white flex items-center gap-3 w-full">
          <TextInput
            type="text"
            value={inputMessage}
            onChange={(e: any) => setInputMessage(e.target.value)}
            disabled={loadingChat}
            className="flex-1"
            inputClassName="text-sm focus:ring-0 focus:ring-offset-0 focus:border-primary"
            placeholder="Type message to support assistant (eg: check credit eligibility for ORD-202)..."
            required
          />
          <Button
            type="submit"
            disabled={loadingChat || !inputMessage.trim()}
            variant="primary"
            size="icon"
            className="h-11 w-11 shrink-0"
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    );
  }

  function renderDashboardPanel() {
    if (loadingInsights && !insights) {
      return (
        <div className="h-[400px] flex flex-col items-center justify-center text-slate-500 gap-3">
          <Spinner className="h-8 w-8 text-amber-500" />
          <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground animate-pulse">Generating operational SLA alerts...</span>
        </div>
      );
    }

    if (insightsError) {
      return (
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
      );
    }

    if (!insights) return null;

    return (
      <div className="space-y-6 pb-12">
        {/* Dashboard Title Toolbar */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Activity className="h-5 w-5 text-amber-500" />
              SLA Analytics & Proactive Signals
            </h2>
            <p className="text-xs text-slate-500">Snapshot time baseline: 2026-08-16 11:00 AM IST</p>
          </div>

          <button
            onClick={fetchInsights}
            disabled={loadingInsights}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-900 border border-slate-800 active:bg-slate-800 disabled:opacity-40 text-xs text-slate-300 rounded-lg hover:border-slate-700 transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loadingInsights ? 'animate-spin' : ''}`} />
            <span>Sync</span>
          </button>
        </div>

        {/* Scorecards grid */}
        <div className="grid grid-cols-4 gap-4">
          <Card className="p-5 flex items-center space-x-4 bg-card/60">
            <div className="p-3 bg-red-500/10 rounded-xl border border-red-500/25">
              <AlertTriangle className="h-6 w-6 text-red-400" />
            </div>
            <div>
              <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest block">SLA Breaches</span>
              <span className="text-2xl font-bold tracking-tight text-white font-mono">{insights.sla_breaches_count}</span>
            </div>
          </Card>

          <Card className="p-5 flex items-center space-x-4 bg-card/60">
            <div className="p-3 bg-orange-500/10 rounded-xl border border-orange-500/25">
              <AlertTriangle className="h-6 w-6 text-orange-400" />
            </div>
            <div>
              <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest block">SLA Warnings</span>
              <span className="text-2xl font-bold tracking-tight text-white font-mono">{insights.sla_warnings_count}</span>
            </div>
          </Card>

          <Card className="p-5 flex items-center space-x-4 bg-card/60">
            <div className="p-3 bg-amber-500/10 rounded-xl border border-amber-500/25">
              <Clock className="h-6 w-6 text-amber-400" />
            </div>
            <div>
              <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest block">Unassigned Tickets</span>
              <span className="text-2xl font-bold tracking-tight text-white font-mono">{insights.unassigned_tickets_count}</span>
            </div>
          </Card>

          <Card className="p-5 flex items-center space-x-4 bg-card/60">
            <div className="p-3 bg-blue-500/10 rounded-xl border border-blue-500/25">
              <Truck className="h-6 w-6 text-blue-400" />
            </div>
            <div>
              <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest block">Delayed Pickups</span>
              <span className="text-2xl font-bold tracking-tight text-white font-mono">{insights.delayed_pickups_count}</span>
            </div>
          </Card>
        </div>

        {/* Detailed reports */}
        <div className="grid grid-cols-2 gap-6">
          {/* SLA Violations / Warning tickets */}
          <div className="bg-white border border-border rounded-xl p-5 space-y-4 shadow-sm">
            <h3 className="text-xs font-black text-slate-805 tracking-wider uppercase flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-500" />
              Critically Breached / Warning Tickets
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border text-slate-400 uppercase font-bold text-[10px]">
                    <th className="py-2.5">Ticket</th>
                    <th className="py-2.5">Account</th>
                    <th className="py-2.5">Priority</th>
                    <th className="py-2.5 text-right font-mono">Elapsed / SLA Target</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {insights.sla_breaches.map((t: any, i: number) => (
                    <tr key={i} className="hover:bg-slate-50 text-slate-700 transition">
                      <td className="py-3 font-semibold text-slate-800 text-[13px]">
                        {t.ticket_id}
                        <span className="block font-medium text-[10.5px] text-slate-400 max-w-[200px] truncate mt-0.5">{t.subject}</span>
                      </td>
                      <td className="py-3 font-mono">{t.account_id}</td>
                      <td className="py-3 font-bold text-red-600">{t.priority}</td>
                      <td className="py-3 text-right font-mono text-red-605 font-black text-xs">
                        {t.elapsed_minutes}m / {t.sla_target_minutes}m
                      </td>
                    </tr>
                  ))}
                  {insights.sla_warnings.map((t: any, i: number) => (
                    <tr key={i} className="hover:bg-slate-50 text-slate-700 transition">
                      <td className="py-3 font-semibold text-slate-800 text-[13px]">
                        {t.ticket_id}
                        <span className="block font-medium text-[10.5px] text-slate-400 max-w-[200px] truncate mt-0.5">{t.subject}</span>
                      </td>
                      <td className="py-3 font-mono">{t.account_id}</td>
                      <td className="py-3 font-bold text-amber-600">{t.priority}</td>
                      <td className="py-3 text-right font-mono text-amber-605 font-black text-xs">
                        {t.elapsed_minutes}m / {t.sla_target_minutes}m
                      </td>
                    </tr>
                  ))}
                  {insights.sla_breaches.length === 0 && insights.sla_warnings.length === 0 && (
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
          <div className="bg-white border border-border rounded-xl p-5 space-y-4 shadow-sm">
            <h3 className="text-xs font-black text-slate-805 tracking-wider uppercase flex items-center gap-2">
              <Truck className="h-4 w-4 text-blue-500" />
              Delayed Shipment Pickups
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border text-slate-400 uppercase font-bold text-[10px]">
                    <th className="py-2.5">Order</th>
                    <th className="py-2.5">Account</th>
                    <th className="py-2.5">Carrier</th>
                    <th className="py-2.5 text-right font-mono">Delay Mins</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {insights.delayed_pickups.map((o: any, i: number) => (
                    <tr key={i} className="hover:bg-slate-50 text-slate-700 transition">
                      <td className="py-3 font-semibold text-slate-800 text-[13px]">
                        {o.order_id}
                        <span className="block text-[10px] font-bold text-slate-500 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded w-max mt-0.5">
                          {o.status}
                        </span>
                      </td>
                      <td className="py-3 font-mono">{o.account_id}</td>
                      <td className="py-3 font-semibold text-slate-700">{o.carrier}</td>
                      <td className="py-3 text-right font-mono font-black text-amber-600 text-xs">{o.delay_minutes}m</td>
                    </tr>
                  ))}
                  {insights.delayed_pickups.length === 0 && (
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
            <div className="bg-white border border-border rounded-xl p-5 space-y-4 shadow-sm col-span-2">
              <h3 className="text-xs font-black text-slate-805 tracking-wider uppercase flex items-center gap-2">
                <MapPin className="h-4 w-4 text-emerald-600" />
                Carrier Failure Scorecard (Tenant Aggregates)
              </h3>

              <div className="grid grid-cols-4 gap-4 pt-1">
                {Object.entries(insights.carrier_scorecard).map(([name, stats]: [string, any]) => {
                  const failureRatePercent = Math.round(stats.failure_rate * 100);
                  const isHighFailure = failureRatePercent >= 15;

                  return (
                    <div key={name} className="p-4 bg-slate-50/50 border border-border rounded-xl space-y-2 shadow-sm">
                      <span className="font-bold text-xs text-slate-700 block font-mono">{name}</span>
                      <div className="flex items-baseline justify-between pt-1">
                        <span className="text-[10px] text-slate-400 block font-bold">Failure Rate</span>
                        <span className={`text-sm font-black font-mono ${isHighFailure ? 'text-red-650' : 'text-emerald-700'}`}>
                          {failureRatePercent}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-full ${isHighFailure ? 'bg-red-500' : 'bg-green-500'}`}
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
}
