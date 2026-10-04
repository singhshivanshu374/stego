import React, { useState } from 'react';
import { api } from '../api/client';
import { Key, Mail, LogIn, UserPlus, CheckCircle2 } from 'lucide-react';
import clsx from 'clsx';

export function AuthScreen({ onLogin }: { onLogin: (token: string) => void }) {
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [registeredKey, setRegisteredKey] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      if (isLogin) {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        
        const data = await api.login(formData);
        onLogin(data.access_token);
      } else {
        const data = await api.register({ username, password });
        setRegisteredKey(data.private_key_pem);
        // Automatically download the PEM file
        const blob = new Blob([data.private_key_pem], { type: 'application/x-pem-file' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${username}_private_key.pem`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setIsLoading(false);
    }
  };

  const switchToLogin = () => {
    setIsLogin(true);
    setRegisteredKey(null);
    setError('');
    setPassword('');
  };

  if (registeredKey) {
    return (
      <div className="flex items-center justify-center min-h-screen p-md relative w-full overflow-hidden">
        <main className="w-full max-w-[500px] relative z-10 animate-fade-in">
          <div className="bg-surface-container border border-outline-variant rounded-lg p-lg shadow-elevated">
            <div className="flex flex-col items-center mb-md text-center">
              <div className="w-16 h-16 mb-md rounded-full bg-primary/10 flex items-center justify-center text-primary">
                <CheckCircle2 size={32} />
              </div>
              <h1 className="font-headline-md text-2xl font-semibold text-on-surface mb-xs">Registration Complete</h1>
              <p className="font-body-sm text-sm text-on-surface-variant text-left mt-4 mb-4">
                Your private key has been generated and downloaded as <code className="text-primary bg-primary/10 px-1 rounded">{username}_private_key.pem</code>.
                <br /><br />
                <span className="text-error font-bold">WARNING:</span> This is the ONLY time this key will be provided to you. If you lose it, you will not be able to decode any Mode B messages sent to you.
              </p>
            </div>
            <button 
              onClick={switchToLogin}
              className="w-full btn btn-primary flex items-center justify-center gap-2"
            >
              Proceed to Login <LogIn size={18} />
            </button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen p-md relative w-full overflow-hidden">
      <main className="w-full max-w-[440px] relative z-10 animate-fade-in">
        <div className="bg-surface-container border border-outline-variant rounded-lg p-lg shadow-elevated transition-all duration-300 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-surface-container via-primary-container to-surface-container opacity-80"></div>
          
          <div className="flex flex-col items-center mb-xl text-center mt-4">
            <h1 className="font-headline-md text-3xl font-semibold text-on-surface tracking-tight mb-xs">
              System Access
            </h1>
            <p className="font-body-sm text-[14px] text-on-surface-variant">
              {isLogin ? 'Provide credentials to initialize secure session.' : 'Register new operative credentials.'}
            </p>
          </div>

          {error && (
            <div className="bg-error/10 border border-error/50 text-error p-3 rounded-lg text-sm mb-6 flex items-center gap-2 animate-fade-in">
              <span className="material-symbols-outlined text-[18px]">error</span>
              {error}
            </div>
          )}

          <form className="space-y-6" onSubmit={handleSubmit}>
            <div className="input-group">
              <label className="input-label flex items-center gap-2">
                <Mail size={16} /> USER_ID // USERNAME
              </label>
              <input
                className="input-field"
                placeholder="operator@securestego.net"
                required
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            
            <div className="input-group">
              <label className="input-label flex items-center gap-2">
                <Key size={16} /> AUTH_KEY // PASSWORD
              </label>
              <input
                className="input-field"
                placeholder="••••••••••••••••"
                required
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <div className="pt-4">
              <button 
                className={clsx("w-full btn btn-primary flex items-center justify-center gap-2", isLoading && "opacity-70 cursor-wait")}
                type="submit"
                disabled={isLoading}
              >
                {isLoading ? (
                  <span className="material-symbols-outlined animate-spin">refresh</span>
                ) : isLogin ? (
                  <><LogIn size={18} /> Initialize Session</>
                ) : (
                  <><UserPlus size={18} /> Register Account</>
                )}
              </button>
            </div>
          </form>

          <div className="mt-8 text-center pt-6 border-t border-outline-variant/50">
            <p className="font-body-sm text-[14px] text-on-surface-variant">
              {isLogin ? 'Unregistered operative? ' : 'Already registered? '}
              <button 
                className="text-primary font-medium hover:text-primary-hover hover:underline transition-all ml-1"
                onClick={() => {
                  setIsLogin(!isLogin);
                  setError('');
                }}
                type="button"
              >
                {isLogin ? 'Request Access clearance' : 'Initialize Session'}
              </button>
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
