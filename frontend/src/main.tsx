import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const originalFetch = window.fetch;
window.fetch = async function (input, init) {
  let response = await originalFetch(input, init);
  const urlStr = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url || '';

  if (response.status === 401 &&
    !urlStr.includes('/auth/login') &&
    !urlStr.includes('/auth/mock-login') &&
    !urlStr.includes('/auth/refresh') &&
    !urlStr.includes('/auth/register')) {

    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
      try {
        const refreshRes = await originalFetch(`${API_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken })
        });

        if (refreshRes.ok) {
          const data = await refreshRes.json();
          localStorage.setItem('access_token', data.access_token);
          localStorage.setItem('refresh_token', data.refresh_token);

          // Dispatch event for sync
          window.dispatchEvent(new CustomEvent('token-refreshed', {
            detail: { access_token: data.access_token, refresh_token: data.refresh_token }
          }));

          if (init && init.headers) {
            if (init.headers instanceof Headers) {
              init.headers.set('Authorization', `Bearer ${data.access_token}`);
            } else if (Array.isArray(init.headers)) {
              const authIndex = init.headers.findIndex(h => h[0].toLowerCase() === 'authorization');
              if (authIndex !== -1) {
                init.headers[authIndex] = ['Authorization', `Bearer ${data.access_token}`];
              } else {
                init.headers.push(['Authorization', `Bearer ${data.access_token}`]);
              }
            } else {
              (init.headers as any)['Authorization'] = `Bearer ${data.access_token}`;
            }
          }

          response = await originalFetch(input, init);
        } else {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          localStorage.removeItem('user');
          window.location.href = '/login';
        }
      } catch (err) {
        console.error("Token refresh failed:", err);
      }
    }
  }
  return response;
};

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
