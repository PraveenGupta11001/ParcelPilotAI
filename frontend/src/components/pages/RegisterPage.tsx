import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import parcelPilotLogo from '../../assets/parcelpilot.png';
import { Button, TextInput, Select } from '../ui';

interface RegisterPageProps {
    API_URL: string;
    setToken: (token: string | null) => void;
    setRefreshToken: (token: string | null) => void;
    setUser: (user: any) => void;
}

export default function RegisterPage({ API_URL, setToken, setRefreshToken, setUser }: RegisterPageProps) {
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [role, setRole] = useState('customer');
    const [accountId, setAccountId] = useState('ACCT-001');
    const [errorMsg, setErrorMsg] = useState('');
    const [successMsg, setSuccessMsg] = useState('');
    const navigate = useNavigate();

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        setErrorMsg('');
        setSuccessMsg('');

        try {
            const res = await fetch(`${API_URL}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    full_name: fullName,
                    email: email.trim(),
                    password,
                    role,
                    account_id: role === 'customer' ? accountId.trim() || null : null
                })
            });

            if (res.ok) {
                setSuccessMsg('Account created successfully! Logging you in...');

                // Auto-login after registration
                const loginRes = await fetch(`${API_URL}/auth/mock-login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: email.trim(), password })
                });

                if (loginRes.ok) {
                    const data = await loginRes.json();
                    localStorage.setItem('access_token', data.access_token);
                    localStorage.setItem('refresh_token', data.refresh_token);
                    localStorage.setItem('user', JSON.stringify(data.user));
                    setToken(data.access_token);
                    setRefreshToken(data.refresh_token);
                    setUser(data.user);
                    setTimeout(() => {
                        navigate('/chat');
                    }, 1000);
                } else {
                    setTimeout(() => {
                        navigate('/login');
                    }, 1000);
                }
            } else {
                const err = await res.json();
                setErrorMsg(err.detail || 'Registration failed.');
            }
        } catch (err) {
            setErrorMsg('Backend connection error. Make sure FastAPI server is running.');
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-4 bg-background text-foreground font-sans z-10">
            <div className="w-full max-w-md bg-white border border-border rounded-2xl shadow-xl p-8 relative z-10">
                <div className="flex flex-col items-center justify-center mb-4">
                    <img src={parcelPilotLogo} alt="ParcelPilot AI" className="w-20 h-20 mb-2 rounded-full shadow-md bg-white p-1 object-contain" />
                </div>
                <h2 className="text-2xl font-black text-center tracking-tight mb-1 text-slate-800">Create Account</h2>
                <p className="text-xs text-muted-foreground font-medium text-center mb-8">
                    Sign up to access ParcelPilot AI Support
                </p>

                <form onSubmit={handleRegister} className="space-y-4">
                    <div>
                        <label className="block text-[10px] font-black text-muted-foreground uppercase tracking-widest mb-2">Full Name</label>
                        <TextInput
                            type="text"
                            value={fullName}
                            onChange={(e: any) => setFullName(e.target.value)}
                            inputClassName="text-xs font-bold"
                            placeholder="eg: John Doe"
                            required
                        />
                    </div>
                    <div>
                        <label className="block text-[10px] font-black text-muted-foreground uppercase tracking-widest mb-2">Email Address</label>
                        <TextInput
                            type="email"
                            value={email}
                            onChange={(e: any) => setEmail(e.target.value)}
                            inputClassName="text-xs font-bold"
                            placeholder="eg: john@example.com"
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
                    <div>
                        <label className="block text-[10px] font-black text-muted-foreground uppercase tracking-widest mb-2">Role Type</label>
                        <Select
                            value={role}
                            onChange={(value: string) => setRole(value)}
                            options={[
                                { value: 'customer', label: 'Customer (Shipper)' },
                                { value: 'internal_support', label: 'Internal Support Agent' },
                                { value: 'internal_lead', label: 'Internal Ops Leader (Manager)' }
                            ]}
                            className="text-xs font-bold"
                        />
                    </div>

                    {role === 'customer' && (
                        <div>
                            <label className="block text-[10px] font-black text-muted-foreground uppercase tracking-widest mb-2">Account ID (SLA Scope)</label>
                            <Select
                                value={accountId}
                                onChange={(value: string) => setAccountId(value)}
                                options={[
                                    { value: 'ACCT-001', label: 'ACCT-001 (Northstar Logistics)' },
                                    { value: 'ACCT-002', label: 'ACCT-002 (LumenWorks)' },
                                    { value: 'ACCT-003', label: 'ACCT-003 (Beacon Retail)' },
                                    { value: 'ACCT-004', label: 'ACCT-004 (Axis Corp)' }
                                ]}
                                className="text-xs font-bold"
                            />
                            <span className="text-[10px] text-muted-foreground mt-2 block">
                                Preconfigured client organization scope for security boundary checks.
                            </span>
                        </div>
                    )}

                    {errorMsg && (
                        <div className="text-xs text-red-500 bg-red-50/50 border border-red-200 p-3 rounded-xl font-bold">
                            {errorMsg}
                        </div>
                    )}

                    {successMsg && (
                        <div className="text-xs text-green-700 bg-green-50/50 border border-green-200 p-3 rounded-xl font-bold">
                            {successMsg}
                        </div>
                    )}

                    <Button
                        type="submit"
                        variant="primary"
                        className="w-full text-xs font-black uppercase tracking-widest bg-emerald-600 hover:bg-emerald-700 text-white"
                    >
                        Register Account
                    </Button>
                </form>

                <div className="mt-6 text-center text-xs">
                    <span className="text-muted-foreground">Already have an account? </span>
                    <button
                        onClick={() => navigate('/login')}
                        className="font-bold text-emerald-650 hover:text-emerald-700 underline cursor-pointer"
                    >
                        Sign In Here
                    </button>
                </div>
            </div>
        </div>
    );
}
