import React, { useState, useRef } from 'react';
import { Header, Footer, TabSwitcher } from './SharedLayout';
import { Uploader } from './Uploader';
import { RecentActivityTable } from './RecentActivityTable';
import { api } from '../api/client';
import { LockOpen, Key, FileCode, Shield, UploadCloud } from 'lucide-react';

export function DecodeScreen({ onLogout }: { onLogout: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<'password' | 'user_bound'>('password');
  const [password, setPassword] = useState('');
  const [privateKeyFile, setPrivateKeyFile] = useState<File | null>(null);
  const [privateKeyContent, setPrivateKeyContent] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [decryptedMessage, setDecryptedMessage] = useState('');
  
  const pemInputRef = useRef<HTMLInputElement>(null);

  const handlePrivateKeyUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setPrivateKeyFile(file);
      const reader = new FileReader();
      reader.onload = (e) => setPrivateKeyContent(e.target?.result as string);
      reader.readAsText(file);
    }
  };

  const handleDecode = async () => {
    setError('');
    setDecryptedMessage('');
    
    if (!file) return setError('Please select a stego image to decode.');
    if (mode === 'password' && !password) return setError('Please enter the decryption key.');
    if (mode === 'user_bound' && !privateKeyContent) return setError('Please upload your private key (.pem file).');

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('image', file);
      
      if (mode === 'password') {
        formData.append('password', password);
      } else {
        formData.append('private_key', privateKeyContent);
      }

      const data = await api.decode(formData);
      setDecryptedMessage(data.message);
    } catch (err: any) {
      setError(err.message || 'Decoding failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-grow flex flex-col w-full">
      <Header onLogout={onLogout} />
      <main className="flex-grow w-full max-w-container-max mx-auto px-gutter py-xl flex flex-col items-center">
        <TabSwitcher activeTab="decode" />
        
        <div className="w-full max-w-4xl bg-surface border border-outline-variant rounded-xl shadow-2xl overflow-hidden flex flex-col md:flex-row">
          
          {/* Left Column: Uploader */}
          <div className="flex-1 p-lg border-b md:border-b-0 md:border-r border-outline-variant flex flex-col">
            <div className="mb-md">
              <h2 className="font-headline-sm text-2xl text-on-surface">Encrypted Media</h2>
              <p className="font-body-sm text-[14px] text-on-surface-variant mt-xs">Upload a stego-image to extract hidden data.</p>
            </div>
            <Uploader onFileSelect={setFile} selectedFile={file} />
          </div>

          {/* Right Column: Settings & Output */}
          <div className="flex-1 p-lg bg-surface-container-low flex flex-col justify-between gap-md">
            
            {/* Algorithm Standard - Static per requirements */}
            <div className="bg-[#121820] border border-[#2D3748] rounded-xl p-md flex flex-col gap-sm shadow-sm">
              <label className="font-label-code text-[13px] text-on-surface flex items-center gap-xs">
                <FileCode size={16} /> Algorithm Standard
              </label>
              <div className="w-full bg-surface-container border border-outline-variant rounded-lg p-sm font-body-sm text-[14px] text-on-surface-variant bg-surface-container-high cursor-not-allowed text-center">
                LSB (fixed)
              </div>
            </div>

            {/* Decryption Settings */}
            <div className="bg-[#121820] border border-[#2D3748] rounded-xl p-md flex flex-col gap-md shadow-sm">
              <div className="flex items-center justify-between">
                <label className="font-label-code text-[13px] text-on-surface flex items-center gap-xs">
                  <Shield size={16} /> Decryption Key
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
                      placeholder="Enter decryption password" 
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                    <Key className="absolute left-sm top-1/2 -translate-y-1/2 text-on-surface-variant" size={18} />
                  </div>
                ) : (
                  <div className="flex flex-col gap-2">
                    <button 
                      onClick={() => pemInputRef.current?.click()}
                      className="w-full bg-surface-container border border-dashed border-outline-variant hover:border-primary/50 hover:bg-surface-bright rounded-lg p-3 text-sm text-on-surface flex items-center justify-center gap-2 transition-all cursor-pointer"
                    >
                      <UploadCloud size={18} /> 
                      {privateKeyFile ? privateKeyFile.name : 'Upload Private Key (.pem)'}
                    </button>
                    <input 
                      ref={pemInputRef}
                      type="file" 
                      accept=".pem"
                      onChange={handlePrivateKeyUpload}
                      className="hidden"
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Extracted Data Area */}
            <div className="bg-[#121820] border border-[#2D3748] rounded-xl p-md flex flex-col gap-sm shadow-sm flex-grow">
              <label className="font-label-code text-[13px] text-on-surface flex items-center gap-xs">
                <LockOpen size={16} /> Extracted Data
              </label>
              <div className="w-full h-full bg-[#090C10] border border-outline-variant rounded-lg p-sm font-label-code text-[13px] text-on-surface min-h-[120px] overflow-auto">
                {error ? (
                  <div className="text-error">{error}</div>
                ) : decryptedMessage ? (
                  <div className="text-primary">{decryptedMessage}</div>
                ) : (
                  <div className="text-on-surface-variant/50 italic">Awaiting decryption...</div>
                )}
              </div>
            </div>

            <button 
              onClick={handleDecode}
              disabled={loading || !file}
              className="w-full bg-secondary-container hover:bg-[#0455b5] disabled:opacity-50 disabled:cursor-not-allowed text-[#FFFFFF] py-md rounded-lg font-headline-sm text-[16px] flex items-center justify-center gap-sm transition-colors mt-md shadow-[0_0_15px_rgba(5,102,217,0.2)]"
            >
              <LockOpen size={20} /> Extract & Decrypt
            </button>
          </div>
        </div>

        <RecentActivityTable key={decryptedMessage ? 'update' : 'idle'} />
      </main>
      <Footer />
    </div>
  );
}
