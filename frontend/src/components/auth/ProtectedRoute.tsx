import React from 'react';
import { Navigate } from 'react-router-dom';

interface UserProfile {
    user_id: string;
    email: string;
    role: string;
    account_id: string | null;
    full_name: string;
}

interface ProtectedRouteProps {
    children: React.ReactNode;
    user: UserProfile | null;
}

export default function ProtectedRoute({ children, user }: ProtectedRouteProps) {
    const token = localStorage.getItem('access_token');
    if (!token || !user) {
        return <Navigate to="/login" replace />;
    }
    return <>{children}</>;
}
