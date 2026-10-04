import React, { useCallback, useState } from 'react';
import { Upload, Image as ImageIcon, X } from 'lucide-react';
import clsx from 'clsx';

interface UploaderProps {
  onFileSelect: (file: File | null) => void;
  selectedFile: File | null;
  accept?: string;
  label?: string;
}

export function Uploader({ 
  onFileSelect, 
  selectedFile, 
  accept = "image/png",
  label = "Click or drag an image to this area to upload" 
}: UploaderProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setIsDragging(true);
    } else if (e.type === 'dragleave') {
      setIsDragging(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onFileSelect(e.dataTransfer.files[0]);
    }
  }, [onFileSelect]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFileSelect(e.target.files[0]);
    }
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onFileSelect(null);
  };

  return (
    <div 
      className={clsx(
        'flex-grow w-full border-2 border-dashed rounded-xl flex flex-col items-center justify-center transition-all cursor-pointer min-h-[300px]',
        isDragging 
          ? 'border-primary bg-primary/10' 
          : 'border-outline-variant bg-[#0E131A] hover:bg-surface-container-highest hover:border-primary/50'
      )}
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
      onClick={() => document.getElementById('file-upload')?.click()}
    >
      <input 
        id="file-upload" 
        type="file" 
        accept={accept}
        style={{ display: 'none' }}
        onChange={handleChange}
      />
      
      {selectedFile ? (
        <div className="flex flex-col items-center animate-fade-in p-md">
          <div className="flex items-center justify-center w-16 h-16 rounded-full bg-primary/20 text-primary mb-sm">
            <ImageIcon size={32} />
          </div>
          <span className="font-headline-sm text-lg text-on-surface mb-xs font-semibold text-center break-all">
            {selectedFile.name}
          </span>
          <span className="font-label-code text-sm text-on-surface-variant mb-md">
            {(selectedFile.size / 1024).toFixed(1)} KB
          </span>
          <button 
            onClick={handleClear}
            className="flex items-center gap-2 px-md py-sm bg-surface border border-outline-variant hover:border-error hover:text-error text-on-surface-variant rounded-lg transition-colors font-body-sm text-[14px]"
          >
            <X size={16} /> Remove File
          </button>
        </div>
      ) : (
        <div className="flex flex-col items-center p-md text-center">
          <div className="flex items-center justify-center w-16 h-16 rounded-full bg-surface border border-outline-variant text-primary mb-md shadow-sm">
            <Upload size={28} />
          </div>
          <p className="font-body-sm text-[14px] text-on-surface-variant max-w-[200px] leading-relaxed">
            {label}
          </p>
          <p className="font-label-code text-[11px] text-on-surface-variant/50 mt-sm">
            Supports {accept}
          </p>
        </div>
      )}
    </div>
  );
}
