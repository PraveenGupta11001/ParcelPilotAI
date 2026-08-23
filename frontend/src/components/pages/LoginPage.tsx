import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import parcelPilotLogo from '../../assets/parcelpilot.png';
import { Button, TextInput } from '../ui';

interface LoginPageProps {
    API_URL: string;
    setToken: (token: string | null) => void;
    setRefreshToken: (token: string | null) => void;
    setUser: (user: any) => void;
}

export default function LoginPage({ API_URL, setToken, setRefreshToken, setUser }: LoginPageProps) {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loginError, setLoginError] = useState('');
    const navigate = useNavigate();

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
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token);
                localStorage.setItem('user', JSON.stringify(data.user));
                setToken(data.access_token);
                setRefreshToken(data.refresh_token);
                setUser(data.user);

                // Navigation: if customer, go to /chat, if internal, go to /chat (or dashboard)
                navigate('/chat');
            } else {
                const err = await res.json();
                setLoginError(err.detail || 'Login failed.');
            }
        } catch (err) {
            setLoginError('Backend connection error. Make sure FastAPI server is running.');
        }
    };

    const handleRoleSwap = (roleKey: string) => {
        const roles: Record<string, any> = {
            'cust-northstar': { email: 'northstar@parcelpilot.ai', password: 'password123' },
            'cust-lumenworks': { email: 'lumenworks@parcelpilot.ai', password: 'password123' },
            'cust-beacon': { email: 'beacon@parcelpilot.ai', password: 'password123' },
            'agent-maya': { email: 'maya@parcelpilot.ai', password: 'password123' },
            'lead-rohit': { email: 'rohit@parcelpilot.ai', password: 'password123' }
        };
        handleLogin(undefined, roles[roleKey]);
    };

    return (
        <div className="min-h-screen flex flex-col items-center justify-center p-4 text-foreground font-sans z-10">
            <div className="w-full max-w-md bg-white border border-border rounded-2xl shadow-xl p-8 relative z-10">
                <div className="flex flex-col items-center mb-6">
                    <img src={parcelPilotLogo} alt="ParcelPilot AI" className="w-24 h-24 mb-4 rounded-full shadow-lg bg-white p-1.5 object-contain" />
                    <h2 className="text-2xl font-black text-center tracking-tight mb-1 text-slate-800">ParcelPilot Support</h2>
                    <p className="text-xs text-muted-foreground font-medium text-center">Good helper, one place for all parcel‑related queries.</p>
                </div>

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
                            autoFocus
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
                        <div className="text-xs text-red-500 bg-red-50/50 border border-red-205 p-3 rounded-xl font-bold">
                            {loginError}
                        </div>
                    )}

                    <Button
                        type="submit"
                        variant="primary"
                        className="w-full text-xs font-black uppercase tracking-widest bg-emerald-600 hover:bg-emerald-700 text-white"
                    >
                        Sign In
                    </Button>
                </form>

                <div className="mt-4 text-center">
                    <button
                        onClick={() => navigate('/register')}
                        className="text-xs font-bold text-emerald-600 hover:text-emerald-700 underline cursor-pointer"
                    >
                        Create an Account (Register)
                    </button>
                </div>

                <div className="mt-8 border-t border-border pt-6">
                    <p className="text-[10px] font-black text-muted-foreground uppercase tracking-widest mb-4 text-center">
                        Quick Role Switcher Seeding
                    </p>
                    <div className="grid grid-cols-2 gap-3 text-[11px]">
                        <button
                            onClick={() => handleRoleSwap('cust-northstar')}
                            className="p-3 border border-border hover:border-emerald-500/40 rounded-xl bg-slate-50 hover:bg-slate-100 text-left transition cursor-pointer"
                        >
                            <div className="font-bold text-slate-800 flex items-center gap-1">💼 <span>Northstar Cust</span></div>
                            <span className="block text-[9px] text-muted-foreground font-bold mt-1 uppercase tracking-wider">ACCT-001 Enterprise</span>
                        </button>
                        <button
                            onClick={() => handleRoleSwap('cust-lumenworks')}
                            className="p-3 border border-border hover:border-emerald-500/40 rounded-xl bg-slate-50 hover:bg-slate-100 text-left transition cursor-pointer"
                        >
                            <div className="font-bold text-slate-800 flex items-center gap-1">⚡ <span>LumenWorks Cust</span></div>
                            <span className="block text-[9px] text-muted-foreground font-bold mt-1 uppercase tracking-wider">ACCT-002 Growth</span>
                        </button>
                        <button
                            onClick={() => handleRoleSwap('cust-beacon')}
                            className="p-3 border border-border hover:border-emerald-500/40 rounded-xl bg-slate-50 hover:bg-slate-100 text-left transition cursor-pointer"
                        >
                            <div className="font-bold text-slate-800 flex items-center gap-1">🛍️ <span>Beacon Cust</span></div>
                            <span className="block text-[9px] text-muted-foreground font-bold mt-1 uppercase tracking-wider">ACCT-003 Standard</span>
                        </button>
                        <button
                            onClick={() => handleRoleSwap('agent-maya')}
                            className="p-3 border border-border hover:border-emerald-500/40 rounded-xl bg-slate-50 hover:bg-slate-100 text-left transition cursor-pointer"
                        >
                            <div className="font-bold text-slate-800 flex items-center gap-1">🙋 <span>Maya Agent</span></div>
                            <span className="block text-[9px] text-muted-foreground font-bold mt-1 uppercase tracking-wider">Internal Ops</span>
                        </button>
                        <button
                            onClick={() => handleRoleSwap('lead-rohit')}
                            className="p-3 border border-border hover:border-emerald-500/40 rounded-xl bg-slate-50 hover:bg-slate-100 text-left transition col-span-2 cursor-pointer"
                        >
                            <div className="font-bold text-slate-800 flex items-center gap-1">👑 <span>Rohit Lead</span></div>
                            <span className="block text-[9px] text-muted-foreground font-bold mt-1 uppercase tracking-wider">Internal Operations Team Lead</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
