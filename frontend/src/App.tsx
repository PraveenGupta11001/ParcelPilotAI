import React, { useState, useEffect } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useNavigate,
  useParams
} from 'react-router-dom';

import LoginPage from './components/pages/LoginPage';
import RegisterPage from './components/pages/RegisterPage';
import DashboardPage from './components/pages/DashboardPage';
import ChatPanel from './components/chat/ChatPanel';
import ProtectedRoute from './components/auth/ProtectedRoute';
import MainLayout from './components/layout/MainLayout';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface UserProfile {
  user_id: string;
  email: string;
  role: string;
  account_id: string | null;
  full_name: string;
}

interface SessionItem {
  id: number;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

function ChatPanelWrapper({ API_URL, token, user, fetchSessions, fetchInsights }: any) {
  const { chatId } = useParams<{ chatId: string }>();
  const navigate = useNavigate();
  return (
    <ChatPanel
      API_URL={API_URL}
      token={token}
      user={user}
      activeSessionId={chatId}
      setActiveSessionId={(id) => {
        if (id) navigate(`/chat/${id}`);
        else navigate('/chat');
      }}
      fetchSessions={fetchSessions}
      fetchInsights={fetchInsights}
    />
  );
}

function AppContent() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [user, setUser] = useState<UserProfile | null>(
    localStorage.getItem('user') ? JSON.parse(localStorage.getItem('user')!) : null
  );

  const [showDocViewer, setShowDocViewer] = useState(false);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);

  const [insights, setInsights] = useState<any>(null);
  const [loadingInsights, setLoadingInsights] = useState(false);
  const [insightsError, setInsightsError] = useState('');

  const navigate = useNavigate();

  useEffect(() => {
    document.title = "ParcelPilot AI Support";
  }, []);

  useEffect(() => {
    if (token && user) {
      fetchSessions();
      if (user.role !== 'customer') {
        fetchInsights();
      }
    }
  }, [token, user]);

  const fetchSessions = async () => {
    if (!token) return;
    setLoadingSessions(true);
    try {
      const res = await fetch(`${API_URL}/chat/sessions`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
      }
    } catch (e) {
      console.error('Failed to load recent sessions', e);
    } finally {
      setLoadingSessions(false);
    }
  };

  const fetchInsights = async () => {
    if (!token) return;
    setLoadingInsights(true);
    setInsightsError('');
    try {
      const res = await fetch(`${API_URL}/insights`, {
        headers: { 'Authorization': `Bearer ${token}` }
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

  const deleteSession = async (sessionId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Delete this historical chat session?')) return;
    try {
      const res = await fetch(`${API_URL}/chat/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        setSessions(prev => prev.filter(s => s.id !== sessionId));
        // Check if the current route matches the deleted session
        if (window.location.pathname === `/chat/${sessionId}`) {
          navigate('/chat');
        }
      }
    } catch (err) {
      alert('Network failure deleting session.');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
    setSessions([]);
    navigate('/login');
  };

  return (
    <Routes>
      <Route
        path="/login"
        element={<LoginPage API_URL={API_URL} setToken={setToken} setUser={setUser} />}
      />
      <Route
        path="/register"
        element={<RegisterPage API_URL={API_URL} setToken={setToken} setUser={setUser} />}
      />

      {/* Protected Routes wrapped in MainLayout */}
      <Route
        path="/chat"
        element={
          <ProtectedRoute user={user}>
            <MainLayout
              user={user}
              token={token}
              handleLogout={handleLogout}
              sessions={sessions}
              loadingSessions={loadingSessions}
              deleteSession={deleteSession}
              showDocViewer={showDocViewer}
              setShowDocViewer={setShowDocViewer}
            >
              <ChatPanel
                API_URL={API_URL}
                token={token}
                user={user}
                activeSessionId={undefined}
                setActiveSessionId={(id) => {
                  if (id) navigate(`/chat/${id}`);
                  else navigate('/chat');
                }}
                fetchSessions={fetchSessions}
                fetchInsights={fetchInsights}
              />
            </MainLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/chat/:chatId"
        element={
          <ProtectedRoute user={user}>
            <MainLayout
              user={user}
              token={token}
              handleLogout={handleLogout}
              sessions={sessions}
              loadingSessions={loadingSessions}
              deleteSession={deleteSession}
              showDocViewer={showDocViewer}
              setShowDocViewer={setShowDocViewer}
            >
              <ChatPanelWrapper
                API_URL={API_URL}
                token={token}
                user={user}
                fetchSessions={fetchSessions}
                fetchInsights={fetchInsights}
              />
            </MainLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/dashboard"
        element={
          <ProtectedRoute user={user}>
            {user?.role !== 'customer' ? (
              <MainLayout
                user={user}
                token={token}
                handleLogout={handleLogout}
                sessions={sessions}
                loadingSessions={loadingSessions}
                deleteSession={deleteSession}
                showDocViewer={showDocViewer}
                setShowDocViewer={setShowDocViewer}
              >
                <DashboardPage
                  insights={insights}
                  loadingInsights={loadingInsights}
                  insightsError={insightsError}
                  fetchInsights={fetchInsights}
                />
              </MainLayout>
            ) : (
              <Navigate to="/chat" replace />
            )}
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}
