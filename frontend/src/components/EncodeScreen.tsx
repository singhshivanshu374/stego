import React, { useState, useEffect, useRef } from 'react';
import { Header, Footer, TabSwitcher } from './SharedLayout';
import { Uploader } from './Uploader';
import { RecentActivityTable } from './RecentActivityTable';
import { api } from '../api/client';
import { Shield, Key, Download, RefreshCw, UserSearch } from 'lucide-react';
import clsx from 'clsx';

export function EncodeScreen({ onLogout }: { onLogout: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState('');
  const [mode, setMode] = useState<'password' | 'user_bound'>('password');
  const [password, setPassword] = useState('');
  const [recipient, setRecipient] = useState('');
  
  const [maxCapacity, setMaxCapacity] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [downloadUrl, setDownloadUrl] = useState('');

  // User search
  const [userQuery, setUserQuery] = useState('');
  const [userResults, setUserResults] = useState<string[]>([]);
  const searchDebounce = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const currentPayloadBytes = new TextEncoder().encode(message).length;

  useEffect(() => {
    if (!file) {
      setMaxCapacity(0);
      return;
    }

    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      // Backend capacity logic: width * height * 3 // 8 - 5 bytes
      const capacity = Math.floor((img.width * img.height * 3) / 8) - 5;
      setMaxCapacity(capacity);
      URL.revokeObjectURL(url);
    };
    img.src = url;
  }, [file]);

  const handleUserSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const q = e.target.value;
    setUserQuery(q);
    setRecipient(q);
    
    if (searchDebounce.current) clearTimeout(searchDebounce.current);
    
    searchDebounce.current = setTimeout(async () => {
      if (q.trim()) {
        try {
          const results = await api.searchUsers(q);
          setUserResults(results);
        } catch {
          setUserResults([]);
        }
      } else {
        setUserResults([]);
      }
    }, 300);
  };

  const handleEncode = async () => {
    setError('');
    setDownloadUrl('');
    
    if (!file) return setError('Please select a carrier image.');
    if (!message) return setError('Please enter a secret payload.');
    if (currentPayloadBytes > maxCapacity) return setError('Payload exceeds image capacity.');
    
    if (mode === 'password' && !password) return setError('Please enter an encryption key.');
    if (mode === 'user_bound' && !recipient) return setError('Please specify a recipient username.');

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('image', file);
      formData.append('message', message);
      formData.append('mode', mode);
      
      if (mode === 'password') {
        formData.append('password', password);
      } else {
        formData.append('recipient_username', recipient);
      }

      const data = await api.encode(formData);
      setDownloadUrl(data.download_url);
    } catch (err: any) {
      setError(err.message || 'Encoding failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-grow flex flex-col w-full">
      <Header onLogout={onLogout} />
      <main className="flex-grow w-full max-w-container-max mx-auto px-gutter py-xl flex flex-col items-center">
        <TabSwitcher activeTab="encode" />
        
        <div className="w-full max-w-4xl bg-surface border border-outline-variant rounded-xl shadow-2xl overflow-hidden flex flex-col md:flex-row">
          
          {/* Left Column: Uploader */}
          <div className="flex-1 p-lg border-b md:border-b-0 md:border-r border-outline-variant flex flex-col">
            <div className="mb-md">
              <h2 className="font-headline-sm text-2xl text-on-surface">Carrier Media</h2>
              <p className="font-body-sm text-[14px] text-on-surface-variant mt-xs">Upload the image to hide data within.</p>
            </div>
            <Uploader onFileSelect={setFile} selectedFile={file} />
          </div>

          {/* Right Column: Settings */}
          <div className="flex-1 p-lg bg-surface-container-low flex flex-col justify-between">
            <div className="flex flex-col gap-md">
              
              {/* Secret Payload Area */}
              <div className="bg-[#121820] border border-[#2D3748] rounded-xl p-md flex flex-col gap-sm shadow-sm relative">
                <label className="font-label-code text-[13px] text-on-surface flex items-center gap-xs">
                  <span className="material-symbols-outlined text-[16px]">subject</span>
                  Secret Payload
                </label>
                <textarea 
                  className="w-full bg-surface-container border border-outline-variant rounded-lg p-sm font-body-sm text-[14px] text-on-surface placeholder-on-surface-variant/50 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all resize-none min-h-[120px]" 
                  placeholder="Enter the text you wish to hide..."
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                />
                <div className="flex justify-end">
                  <span className={clsx(
                    "font-label-code text-[11px]",
                    currentPayloadBytes > maxCapacity ? "text-error font-bold" : "text-on-surface-variant"
                  )}>
                    {currentPayloadBytes} / {maxCapacity || '-'} bytes
                  </span>
                </div>
              </div>

              {/* Encryption Settings */}
              <div className="bg-[#121820] border border-[#2D3748] rounded-xl p-md flex flex-col gap-md shadow-sm">
                <div className="flex items-center justify-between">
                  <label className="font-label-code text-[13px] text-on-surface flex items-center gap-xs">
                    <Shield size={16} /> Encryption Settings
                  </label>
                  <select 
                    value={mode} 
                    onChange={(e) => setMode(e.target.value as 'password'|'user_bound')}
                    className="bg-surface-container border border-outline-variant rounded-md px-2 py-1 text-xs text-on-surface"
                  >
                    <option value="password">Password (Mode A)</option>
                    <option value="user_bound">Specific User (Mode B)</option>
                  </select>
                </div>
                
                <div className="flex flex-col gap-xs mt-sm">
                  {mode === 'password' ? (
                    <div className="relative">
                      <input 
                        className="w-full bg-surface-container border border-outline-variant rounded-lg pl-10 pr-sm py-sm font-body-sm text-[14px] text-on-surface placeholder-on-surface-variant/50 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all" 
                        placeholder="Enter encryption key" 
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                      />
                      <Key className="absolute left-sm top-1/2 -translate-y-1/2 text-on-surface-variant" size={18} />
                    </div>
                  ) : (
                    <div className="relative">
                      <input 
                        className="w-full bg-surface-container border border-outline-variant rounded-lg pl-10 pr-sm py-sm font-body-sm text-[14px] text-on-surface placeholder-on-surface-variant/50 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all" 
                        placeholder="Search recipient username" 
                        type="text"
                        value={userQuery}
                        onChange={handleUserSearch}
                        onBlur={() => setTimeout(() => setUserResults([]), 200)}
                      />
                      <UserSearch className="absolute left-sm top-1/2 -translate-y-1/2 text-on-surface-variant" size={18} />
                      
                      {userResults.length > 0 && (
                        <div className="absolute top-full mt-1 w-full bg-surface-container-high border border-outline-variant rounded-md shadow-lg z-50 overflow-hidden">
                          {userResults.map((u) => (
                            <div 
                              key={u} 
                              className="px-sm py-xs text-sm cursor-pointer hover:bg-primary/20 text-on-surface"
                              onMouseDown={() => {
                                setRecipient(u);
                                setUserQuery(u);
                                setUserResults([]);
                              }}
                            >
                              {u}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {error && <div className="mt-4 text-error text-sm text-center">{error}</div>}

            {downloadUrl ? (
              <button 
                onClick={async () => {
                  try {
                    await api.downloadFile(downloadUrl);
                  } catch (err: any) {
                    setError(err.message || "Failed to download file");
                  }
                }}
                className="w-full mt-lg bg-primary-container hover:bg-primary text-on-primary-fixed py-md rounded-lg font-headline-sm text-[16px] flex items-center justify-center gap-sm transition-colors mt-auto shadow-[0_0_15px_rgba(20,184,166,0.3)] animate-fade-in"
              >
                <Download size={20} /> Download Stego Image
              </button>
            ) : (
              <button 
                onClick={handleEncode}
                disabled={loading || currentPayloadBytes > (maxCapacity || Infinity) || !file}
                className="w-full mt-lg bg-primary-container hover:bg-[#119f8e] disabled:opacity-50 disabled:cursor-not-allowed text-on-primary-fixed py-md rounded-lg font-headline-sm text-[16px] flex items-center justify-center gap-sm transition-colors mt-auto shadow-[0_0_15px_rgba(20,184,166,0.2)]"
              >
                {loading ? <RefreshCw className="animate-spin" size={20} /> : <Shield size={20} />}
                Encode & Download
              </button>
            )}
          </div>
        </div>

        {/* Recent Activity */}
        <RecentActivityTable key={downloadUrl ? 'update' : 'idle'} />
      </main>
      <Footer />
    </div>
  );
}
