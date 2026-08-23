import React, { useState, useEffect, useRef } from 'react';
import { Send, RefreshCw, FileText, ChevronDown, ChevronUp, Activity, Check, Copy } from 'lucide-react';
import { Button, TextInput, EmptyState, ConfirmDialog } from '../ui';
import { toast } from 'sonner';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import parcelPilotLogo from '../../assets/parcelpilot.png';

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

const renderMarkdown = (text: string) => {
    return (
        <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
                p: ({ children }) => <p className="mb-2 last:mb-0" style={{ wordBreak: 'break-word' }}>{children}</p>,
                a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-emerald-600 hover:text-emerald-700 underline font-semibold">{children}</a>,
                strong: ({ children }) => <strong className="font-extrabold text-slate-900">{children}</strong>,
                em: ({ children }) => <em className="italic">{children}</em>,
                code({ node, inline, className, children, ...props }: any) {
                    return inline ? (
                        <code className="bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded font-mono text-xs text-rose-600 font-semibold" {...props}>
                            {children}
                        </code>
                    ) : (
                        <pre className="bg-slate-900 text-slate-100 p-3.5 my-3 rounded-xl font-mono text-xs overflow-x-auto border border-slate-800" {...props}>
                            <code>{children}</code>
                        </pre>
                    );
                },
                table: ({ children }) => <div className="overflow-x-auto my-3 border border-slate-205 rounded-xl"><table className="min-w-full divide-y divide-slate-200 border-collapse bg-white">{children}</table></div>,
                thead: ({ children }) => <thead className="bg-slate-50">{children}</thead>,
                tbody: ({ children }) => <tbody className="divide-y divide-slate-100 bg-white">{children}</tbody>,
                tr: ({ children }) => <tr>{children}</tr>,
                th: ({ children }) => <th className="px-4 py-2 bg-slate-50 text-left text-xs font-bold uppercase tracking-wider text-slate-550 border-b border-slate-200">{children}</th>,
                td: ({ children }) => <td className="px-4 py-2 text-xs text-slate-700 border-b border-slate-100 font-medium">{children}</td>,
                ul: ({ children }) => <ul className="list-disc pl-5 my-2 space-y-1.5 text-sm">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal pl-5 my-2 space-y-1.5 text-sm">{children}</ol>,
                li: ({ children }) => <li className="text-slate-750 font-medium list-item">{children}</li>,
                blockquote: ({ children }) => <blockquote className="border-l-4 border-emerald-500 pl-4 py-1 my-3 bg-slate-50/50 rounded-r text-slate-655 italic">{children}</blockquote>,
                h1: ({ children }) => <h1 className="text-lg font-black text-slate-900 mt-4 mb-2 tracking-tight">{children}</h1>,
                h2: ({ children }) => <h2 className="text-base font-extrabold text-slate-950 mt-3 mb-2 tracking-tight">{children}</h2>,
                h3: ({ children }) => <h3 className="text-sm font-bold text-slate-800 mt-2.5 mb-1.5">{children}</h3>,
            }}
        >
            {text}
        </ReactMarkdown>
    );
};

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
    const [reasoningStatus, setReasoningStatus] = useState<string>('');
    const [liveToolCalls, setLiveToolCalls] = useState<any[]>([]);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Expandable trace states
    const [expandedTrace, setExpandedTrace] = useState<Record<string, boolean>>({});
    const [expandedSection, setExpandedSection] = useState<Record<string, boolean>>({});
    const [copiedId, setCopiedId] = useState<string | null>(null);

    // Confirm dialog modal states
    const [confirmOpen, setConfirmOpen] = useState(false);
    const [confirmProposalId, setConfirmProposalId] = useState<number | null>(null);
    const [confirmMsgId, setConfirmMsgId] = useState<string | null>(null);
    const [confirmActionType, setConfirmActionType] = useState('');
    const [confirmLoading, setConfirmLoading] = useState(false);

    const isCreatingSessionRef = useRef(false);
    const chatInputRef = useRef<HTMLInputElement>(null);

    // Auto-focus on input element when loading completes or session changes
    useEffect(() => {
        if (!loadingChat) {
            const t = setTimeout(() => {
                chatInputRef.current?.focus();
            }, 60);
            return () => clearTimeout(t);
        }
    }, [loadingChat, activeSessionId]);

    // Auto-scroll chat
    useEffect(() => {
        scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, loadingChat]);

    // Load message logs if session ID is set
    useEffect(() => {
        if (activeSessionId) {
            if (isCreatingSessionRef.current) {
                isCreatingSessionRef.current = false;
            } else {
                loadSessionMessages();
            }
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
        setReasoningStatus('Initializing assistant request...');
        setLiveToolCalls([]);

        if (!activeSessionId) {
            isCreatingSessionRef.current = true;
        }

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
                    session_id: activeSessionId || null,
                    stream: true
                })
            });

            if (res.ok) {
                const reader = res.body?.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                const assistantMsgId = Math.random().toString();
                const assistantMsg: Message = {
                    id: assistantMsgId,
                    role: 'assistant',
                    content: '',
                    tool_calls: []
                };
                setMessages(prev => [...prev, assistantMsg]);

                if (reader) {
                    while (true) {
                        const { value, done } = await reader.read();
                        if (done) break;

                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split('\n');
                        buffer = lines.pop() || '';

                        for (const line of lines) {
                            const trimmed = line.trim();
                            if (!trimmed.startsWith('data: ')) continue;

                            try {
                                const jsonStr = trimmed.substring(6);
                                const parsed = JSON.parse(jsonStr);

                                if (parsed.event === 'session_created') {
                                    const newSId = parsed.session_id.toString();
                                    setActiveSessionId(newSId);
                                    window.history.pushState(null, '', `/chat/${newSId}`);
                                    fetchSessions();
                                } else if (parsed.event === 'status') {
                                    setReasoningStatus(parsed.message);
                                } else if (parsed.event === 'tool_call') {
                                    setReasoningStatus(`Executing ${parsed.name}...`);
                                    setLiveToolCalls(prev => {
                                        if (prev.some(tc => tc.tool_name === parsed.name && JSON.stringify(tc.args) === JSON.stringify(parsed.args))) {
                                            return prev;
                                        }
                                        return [...prev, {
                                            tool_name: parsed.name,
                                            args: parsed.args,
                                            output: 'running...'
                                        }];
                                    });
                                } else if (parsed.event === 'tool_result') {
                                    setReasoningStatus(`Completed ${parsed.name} execution`);
                                    setLiveToolCalls(prev => prev.map(tc =>
                                        tc.tool_name === parsed.name ? { ...tc, output: parsed.output } : tc
                                    ));
                                } else if (parsed.event === 'text') {
                                    setMessages(prev => prev.map(m =>
                                        m.id === assistantMsgId ? { ...m, content: parsed.text } : m
                                    ));
                                } else if (parsed.event === 'done') {
                                    setMessages(prev => prev.map(m =>
                                        m.id === assistantMsgId ? {
                                            ...m,
                                            content: parsed.text_response,
                                            tool_calls: parsed.tool_calls
                                        } : m
                                    ));
                                }
                            } catch (e) {
                                console.error('Failed to parse SSE JSON chunk', e);
                            }
                        }
                    }
                }

                setLoadingChat(false);
                setReasoningStatus('');
                setLiveToolCalls([]);
                if (user && user.role !== 'customer') {
                    fetchInsights();
                }

            } else {
                setMessages(prev => [...prev, {
                    id: Math.random().toString(),
                    role: 'assistant',
                    content: '⚠️ **Error: Failed to process query through the backend orchestrator.**\n\nThe server responded with an error status. Please check application settings or API logs.'
                }]);
                setLoadingChat(false);
            }
        } catch (e) {
            setMessages(prev => [...prev, {
                id: Math.random().toString(),
                role: 'assistant',
                content: '⚠️ **Error: API server unreachable.**\n\nPlease check if the backend service is running normally.'
            }]);
            setLoadingChat(false);
        }
    };

    const handleConfirmAction = async (proposalId: number, msgId: string) => {
        setConfirmLoading(true);
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
                toast.success(data.message || `Successfully executed proposal #${proposalId}`);

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
                setConfirmOpen(false);
            } else {
                const err = await res.json();
                toast.error(err.detail || 'Failed to confirm proposal.');
            }
        } catch (e) {
            toast.error('Internal connection error during confirmation stage.');
        } finally {
            setConfirmLoading(false);
        }
    };

    return (
        <div className="flex-1 flex flex-col bg-white border border-border rounded-2xl overflow-hidden shadow-sm h-full">
            {/* Messages Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {messages.length === 0 && !loadingChat && (
                    <div className="h-full flex items-center justify-center py-16">
                        <EmptyState
                            icon={() => (
                                <img src={parcelPilotLogo} alt="ParcelPilot Logo" className="h-7 w-7 object-contain select-none" />
                            )}
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
                                className={`relative px-4 py-3.5 rounded-2xl text-base leading-relaxed ${m.role === 'user'
                                    ? 'bg-emerald-650 text-slate-800 font-bold rounded-tr-none'
                                    : msgText.startsWith('⚠️')
                                        ? 'bg-rose-50 border border-rose-250 text-rose-950 rounded-tl-none shadow-sm shadow-rose-100/50'
                                        : 'bg-slate-50 border border-border text-slate-800 rounded-tl-none shadow-sm'
                                    }`}
                            >
                                {/* Copy to Clipboard button float */}
                                {msgText.trim() && (
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
                                )}

                                {m.role === 'user' ? (
                                    <div className="whitespace-pre-wrap font-medium" style={{ wordBreak: 'break-word' }}>
                                        {msgText}
                                    </div>
                                ) : msgText.trim() ? (
                                    renderMarkdown(msgText)
                                ) : hasCitations ? (
                                    <div className="text-sm font-semibold text-slate-500 italic flex items-center gap-1.5 py-1">
                                        <FileText className="h-4 w-4 animate-pulse text-emerald-600" />
                                        <span>Retrieved the following matching policy reference documents:</span>
                                    </div>
                                ) : hasConfirmations ? (
                                    <div className="text-sm font-semibold text-slate-500 italic flex items-center gap-1.5 py-1">
                                        <span>Proposed a calculated transaction action:</span>
                                    </div>
                                ) : (
                                    <div className="text-sm font-semibold text-slate-500 italic flex items-center gap-1.5 py-1">
                                        <span>AI agent processed calculations / systems lookups:</span>
                                    </div>
                                )}
                            </div>

                            {/* Citations/Traces */}
                            {m.role === 'assistant' && (
                                <div className="w-full mt-2 space-y-2">
                                    {/* Render Confirmations proposal cards */}
                                    {hasConfirmations && m.tool_calls?.map((tc, idx) => {
                                        if (tc.tool_name === 'propose_action') {
                                            let parsed: any = null;
                                            try {
                                                if (typeof tc.output === 'string') {
                                                    parsed = JSON.parse(tc.output);
                                                } else {
                                                    parsed = tc.output;
                                                }
                                            } catch (e) {
                                                console.error('Failed to parse propose_action output', e);
                                                return null;
                                            }
                                            if (!parsed || parsed.error) return null;

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
                                                                onClick={() => {
                                                                    setConfirmProposalId(parsed.proposal_id);
                                                                    setConfirmMsgId(m.id);
                                                                    setConfirmActionType(parsed.action_type || 'Action');
                                                                    setConfirmOpen(true);
                                                                }}
                                                                className="flex-1 py-1.5 bg-emerald-650 text-white font-bold text-xs rounded hover:bg-emerald-700 transition-colors cursor-pointer"
                                                            >
                                                                Confirm Action
                                                            </button>
                                                            <button
                                                                onClick={() => {
                                                                    toast.info('Proposal rejected locally.');
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
                                                if (typeof tc.output === 'string') {
                                                    parsed = JSON.parse(tc.output);
                                                } else {
                                                    parsed = tc.output || [];
                                                }
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
                                                                OUTPUT: {typeof tc.output === 'string'
                                                                    ? (tc.output.length > 250 ? tc.output.substring(0, 250) + '...' : tc.output)
                                                                    : (JSON.stringify(tc.output).length > 250 ? JSON.stringify(tc.output).substring(0, 250) + '...' : JSON.stringify(tc.output))}
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
                    <div className="pl-4 py-2.5 pr-2.5 mx-4 my-2 shrink-0 border border-slate-100 bg-slate-50/50 rounded-xl space-y-2.5 transition-all duration-300">
                        <div className="flex items-center space-x-2 text-xs font-semibold text-emerald-800">
                            <RefreshCw className="h-3.5 w-3.5 animate-spin text-emerald-600 font-extrabold" />
                            <span>{reasoningStatus || 'Analyzing search metrics & database status...'}</span>
                        </div>
                        {liveToolCalls.length > 0 && (
                            <div className="space-y-2 pl-5">
                                <div className="text-[10px] uppercase font-bold text-slate-400 font-sans tracking-wide">Live Tool Executions:</div>
                                {liveToolCalls.map((tc, idx) => {
                                    const isRunning = tc.output === 'running...';
                                    const isFailed = (() => {
                                        if (!tc.output || typeof tc.output !== 'string') return false;
                                        const trimmed = tc.output.trim();
                                        if (trimmed.startsWith('{"error":')) return true;
                                        try {
                                            const parsed = JSON.parse(trimmed);
                                            return parsed && (parsed.error !== undefined || parsed.status === 'error' || parsed.status === 'FAILED');
                                        } catch (e) {
                                            return trimmed.toLowerCase().includes('error');
                                        }
                                    })();

                                    let dotColorClass = 'bg-emerald-500';
                                    let dotAnimationClass = '';
                                    if (isRunning) {
                                        dotAnimationClass = 'animate-pulse';
                                    } else if (isFailed) {
                                        dotColorClass = 'bg-red-500';
                                    }

                                    return (
                                        <div key={idx} className="flex flex-col text-[11px] font-mono text-slate-650 bg-white p-2.5 rounded-lg border border-border shadow-sm animate-fade-in">
                                            <div className="flex items-center justify-between font-bold text-slate-705">
                                                <span className="flex items-center space-x-1.5">
                                                    <span className={`w-1.5 h-1.5 rounded-full ${dotColorClass} ${dotAnimationClass}`}></span>
                                                    <span className={isFailed ? "text-red-700" : "text-emerald-700"}>🔧 {tc.tool_name}()</span>
                                                </span>
                                                {isRunning ? (
                                                    <span className="text-[9px] font-bold text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">RUNNING</span>
                                                ) : isFailed ? (
                                                    <span className="text-[9px] font-bold text-red-600 bg-red-50 px-1.5 py-0.5 rounded border border-red-200">FAILED</span>
                                                ) : (
                                                    <span className="text-[9px] font-bold text-emerald-700 bg-green-50 px-1.5 py-0.5 rounded border border-green-200">COMPLETED</span>
                                                )}
                                            </div>
                                            <div className="text-[10px] text-slate-400 mt-1 font-medium select-all">Args: {JSON.stringify(tc.args)}</div>
                                            {!isRunning && (
                                                <div className="text-[10px] text-slate-500 mt-1 italic border-t border-slate-50 pt-1">
                                                    Output: {typeof tc.output === 'string'
                                                        ? (tc.output.length > 80 ? tc.output.substring(0, 80) + '...' : tc.output)
                                                        : (JSON.stringify(tc.output).length > 80 ? JSON.stringify(tc.output).substring(0, 80) + '...' : JSON.stringify(tc.output))
                                                    }
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        )}
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
                    <Send className="h-4 w-4 text-emerald-600 font-bold" />
                </Button>
            </form>

            <ConfirmDialog
                open={confirmOpen}
                onClose={() => setConfirmOpen(false)}
                onConfirm={() => {
                    if (confirmProposalId !== null && confirmMsgId !== null) {
                        handleConfirmAction(confirmProposalId, confirmMsgId);
                    }
                }}
                title="Confirm Proposal Execution"
                description={`Are you sure you want to finalize and execute the proposed ${confirmActionType.replace(/_/g, ' ')} for proposal #${confirmProposalId}? This action will permanently mutate backend records.`}
                confirmLabel="Execute Action"
                cancelLabel="Cancel"
                variant="success"
                loading={confirmLoading}
            />
        </div>
    );
}
