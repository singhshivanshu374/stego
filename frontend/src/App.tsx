import { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { AuthScreen } from './components/AuthScreen';
import { EncodeScreen } from './components/EncodeScreen';
import { DecodeScreen } from './components/DecodeScreen';
import { setToken, getToken } from './api/client';

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!getToken());
  const navigate = useNavigate();

  // Keep state in sync with token
  useEffect(() => {
    setIsAuthenticated(!!getToken());
  }, []);

  const handleLogin = (token: string) => {
    setToken(token);
    setIsAuthenticated(true);
    navigate('/encode');
  };

  const handleLogout = () => {
    setToken(null);
    setIsAuthenticated(false);
    navigate('/');
  };

  return (
    <Routes>
      <Route 
        path="/" 
        element={
          isAuthenticated 
            ? <Navigate to="/encode" replace /> 
            : <AuthScreen onLogin={handleLogin} />
        } 
      />
      <Route 
        path="/encode" 
        element={
          isAuthenticated 
            ? <EncodeScreen onLogout={handleLogout} /> 
            : <Navigate to="/" replace />
        } 
      />
      <Route 
        path="/decode" 
        element={
          isAuthenticated 
            ? <DecodeScreen onLogout={handleLogout} /> 
            : <Navigate to="/" replace />
        } 
      />
    </Routes>
  );
}

export default App;
