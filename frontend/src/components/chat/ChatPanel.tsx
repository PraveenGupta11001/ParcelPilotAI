import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Send, RefreshCw, FileText, ChevronDown, ChevronUp, Activity, Check, Copy } from 'lucide-react';
import { Button, TextInput, EmptyState } from '../ui';

interface Message {
    id: string;
    role?: 'user' | 'assistant';
    sender?: string; // from backend: "user", "bot"
    text?: string;
    content?: string;
    tool_calls?: any[];
}

interface ChatPanelProps {
    API_URL: string;
    token: string | null;
    user: any;
    activeSessionId: string | undefined;
    setActiveSessionId: (id: string | undefined) => void;
    fetchSessions: () => void;
    fetchInsights: () => void;
}

export default function ChatPanel({
    API_URL,
    token,
    user,
    activeSessionId,
    setActiveSessionId,
    fetchSessions,
    fetchInsights
}: ChatPanelProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [inputMessage, setInputMessage] = useState('');
    const [loadingChat, setLoadingChat] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);
    const navigate = useNavigate();

    // Expandable trace states
    const [expandedTrace, setExpandedTrace] = useState<Record<string, boolean>>({});
    const [expandedSection, setExpandedSection] = useState<Record<string, boolean>>({});
    const [copiedId, setCopiedId] = useState<string | null>(null);

    // Auto-scroll chat
    useEffect(() => {
        scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, loadingChat]);

    // Load message logs if session ID is set
    useEffect(() => {
        if (activeSessionId) {
            loadSessionMessages();
        } else {
            setMessages([]);
        }
    }, [activeSessionId]);

    const loadSessionMessages = async () => {
        setLoadingChat(true);
        try {
            const res = await fetch(`${API_URL}/chat/sessions/${activeSessionId}/messages`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            if (res.ok) {
                const data = await res.json();
                // Convert to standard format
                const formatted = data.map((m: any) => ({
                    id: m.id.toString(),
                    role: m.sender === 'user' ? 'user' : 'assistant',
                    content: m.text,
                    tool_calls: m.tool_calls
                }));
                setMessages(formatted);
            }
        } catch (e) {
            console.error('Failed to load session message history', e);
        } finally {
            setLoadingChat(false);
        }
    };

    const handleCopy = (id: string, text: string) => {
        navigator.clipboard.writeText(text);
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 2000);
    };

    const handleSendMessage = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!inputMessage.trim() || loadingChat) return;

        const userText = inputMessage;
        setInputMessage('');

        const userMsg: Message = {
            id: Math.random().toString(),
            role: 'user',
            content: userText
        };

        setMessages(prev => [...prev, userMsg]);
        setLoadingChat(true);

        try {
            const formattedHistory = messages.map(m => ({
                role: m.role || 'user',
                content: m.content || ''
            }));

            const res = await fetch(`${API_URL}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    message: userText,
                    chat_history: formattedHistory,
                    session_id: activeSessionId ? parseInt(activeSessionId) : null
                })
            });

            if (res.ok) {
                const data = await res.json();

                // If let the backend auto-create session or we had no active session ID
                if (!activeSessionId && data.session_id) {
                    setActiveSessionId(data.session_id.toString());
                    navigate(`/chat/${data.session_id}`);
                    fetchSessions();
                }

                const assistantMsgId = Math.random().toString();
                const assistantMsg: Message = {
                    id: assistantMsgId,
                    role: 'assistant',
                    content: '',
                    tool_calls: data.tool_calls
                };
                setMessages(prev => [...prev, assistantMsg]);

                // Streaming Typewriter effect simulation
                const responseText = data.text_response || '';
                const words = responseText.split(' ');
                let wordIndex = 0;
                let currentText = '';

                const timer = setInterval(() => {
                    if (wordIndex < words.length) {
                        currentText += (wordIndex === 0 ? '' : ' ') + words[wordIndex];
                        setMessages(prev => prev.map(m => m.id === assistantMsgId ? { ...m, content: currentText } : m));
                        wordIndex++;
                    } else {
                        clearInterval(timer);
                        setLoadingChat(false);
                        if (user && user.role !== 'customer') {
                            fetchInsights();
                        }
                    }
                }, 35);

            } else {
                setMessages(prev => [...prev, {
                    id: Math.random().toString(),
                    role: 'assistant',
                    content: 'Error: Failed to process query through the backend orchestrator.'
                }]);
                setLoadingChat(false);
            }
        } catch (e) {
            setMessages(prev => [...prev, {
                id: Math.random().toString(),
                role: 'assistant',
                content: 'Error: API server unreachable.'
            }]);
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

                setMessages(prev => prev.map(m => {
                    if (m.id === msgId && m.tool_calls) {
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
                            content: (m.content || '') + `\n\n✅ **Action Confirmed!** ${data.message}`,
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

    return (
        <div className="flex-1 flex flex-col bg-white border border-border rounded-2xl overflow-hidden shadow-sm h-full">
            {/* Messages Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {messages.length === 0 && !loadingChat && (
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
                    const msgText = m.content || '';

                    return (
                        <div
                            key={m.id}
                            className={`flex flex-col max-w-[85%] relative group ${m.role === 'user' ? 'ml-auto items-end' : 'mr-auto items-start'}`}
                        >
                            <div
                                className={`px-4 py-3.5 rounded-2xl text-base leading-relaxed ${m.role === 'user'
                                    ? 'bg-emerald-650 text-white font-bold rounded-tr-none'
                                    : 'bg-slate-50 border border-border text-slate-800 rounded-tl-none shadow-sm'
                                    }`}
                            >
                                {/* Copy to Clipboard button float */}
                                <button
                                    onClick={() => handleCopy(m.id, msgText)}
                                    className={`absolute top-2.5 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 bg-white hover:bg-slate-100 border border-border rounded-lg cursor-pointer ${m.role === 'user' ? 'text-slate-800 border-none' : 'text-slate-500'}`}
                                    title="Copy message to clipboard"
                                >
                                    {copiedId === m.id ? (
                                        <Check className="h-3 w-3 text-emerald-600" />
                                    ) : (
                                        <Copy className="h-3 w-3" />
                                    )}
                                </button>

                                {/* Handle lines */}
                                {msgText.split('\n').map((para, i) => (
                                    <p key={i} className={para.trim() ? "mb-2 last:mb-0" : "h-2"} style={{ wordBreak: 'break-word' }}>
                                        {para}
                                    </p>
                                ))}
                            </div>

                            {/* Citations/Traces */}
                            {m.role === 'assistant' && (
                                <div className="w-full mt-2 space-y-2">
                                    {/* Render Confirmations proposal cards */}
                                    {hasConfirmations && m.tool_calls?.map((tc, idx) => {
                                        if (tc.tool_name === 'propose_action') {
                                            const parsed = JSON.parse(tc.output);
                                            if (parsed.error) return null;

                                            const isPending = parsed.status === 'PENDING';
                                            const isApproved = parsed.status === 'APPROVED';

                                            return (
                                                <div key={idx} className="p-4 border border-border bg-slate-50 rounded-xl space-y-3">
                                                    <div className="flex items-center justify-between">
                                                        <span className="text-xs text-emerald-600 font-bold uppercase tracking-wider block">
                                                            Proposed: {parsed.action_type}
                                                        </span>
                                                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${isApproved ? 'bg-green-50 text-green-700 border border-green-250' : 'bg-amber-50 text-amber-700 border border-amber-200'
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
                                                                className="flex-1 py-1.5 bg-emerald-650 text-white font-bold text-xs rounded hover:bg-emerald-700 transition-colors cursor-pointer"
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

                                    {/* Citiations */}
                                    {hasCitations && m.tool_calls?.map((tc, idx) => {
                                        if (tc.tool_name === 'search_documents') {
                                            let parsed = [];
                                            try {
                                                parsed = JSON.parse(tc.output);
                                            } catch (e) { return null; }

                                            if ((parsed as any).error || !parsed.length) return null;
                                            const idKey = `${m.id}-citations`;

                                            return (
                                                <div key={idx} className="text-xs">
                                                    <button
                                                        onClick={() => setExpandedSection(prev => ({ ...prev, [idKey]: !prev[idKey] }))}
                                                        className="flex items-center space-x-1.5 text-slate-500 hover:text-slate-800 font-medium py-1 transition-colors"
                                                    >
                                                        <FileText className="h-3.5 w-3.5 text-slate-400" />
                                                        <span>{expandedSection[idKey] ? 'Hide' : 'Show'} Document Citations ({parsed.length})</span>
                                                        {expandedSection[idKey] ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                                                    </button>

                                                    {expandedSection[idKey] && (
                                                        <div className="mt-1 space-y-2 border-l-2 border-border pl-3 pt-1">
                                                            {parsed.map((c: any, cIdx: number) => (
                                                                <div key={cIdx} className="bg-white p-2.5 rounded-lg border border-border shadow-sm">
                                                                    <div className="flex items-center justify-between mb-1.5">
                                                                        <span className="font-bold text-slate-800 block">{c.document_name} [Page: {c.chunk_index + 1}]</span>
                                                                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${c.authority_level === 1 ? 'bg-red-50 text-red-700 border border-red-200' : c.authority_level === 2 ? 'bg-amber-50 text-amber-700 border border-amber-200' : 'bg-slate-100 text-slate-650'
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

                                    {/* Traces */}
                                    {hasTrace && (
                                        <div className="text-xs">
                                            <button
                                                onClick={() => setExpandedTrace(prev => ({ ...prev, [m.id]: !prev[m.id] }))}
                                                className="flex items-center space-x-1.5 text-slate-500 hover:text-slate-850 font-medium py-1 transition-colors"
                                            >
                                                <Activity className="h-3.5 w-3.5 text-slate-400" />
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

                {loadingChat && messages.length > 0 && (
                    <div className="flex items-center space-x-2 text-xs text-slate-600 font-semibold pl-4 py-2">
                        <RefreshCw className="h-3.5 w-3.5 animate-spin text-emerald-600" />
                        <span>AI Agent reasoning & searching database...</span>
                    </div>
                )}
                <div ref={scrollRef}></div>
            </div>

            {/* Input Panel */}
            <form onSubmit={handleSendMessage} className="p-4 border-t border-border bg-white flex items-center gap-3 w-full shrink-0">
                <TextInput
                    type="text"
                    value={inputMessage}
                    onChange={(e: any) => setInputMessage(e.target.value)}
                    disabled={loadingChat}
                    className="flex-1"
                    inputClassName="text-sm focus:ring-0 focus:ring-offset-0 focus:border-emerald-600"
                    placeholder="Type message to support assistant (eg: check credit eligibility for ORD-202)..."
                    required
                />
                <Button
                    type="submit"
                    disabled={loadingChat || !inputMessage.trim()}
                    variant="primary"
                    size="icon"
                    className="h-11 w-11 shrink-0 bg-emerald-650 hover:bg-emerald-700 text-white flex items-center justify-center rounded-xl"
                >
                    <Send className="h-4 w-4" />
                </Button>
            </form>
        </div>
    );
}
