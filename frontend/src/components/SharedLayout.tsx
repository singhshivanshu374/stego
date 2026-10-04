
import { useNavigate } from 'react-router-dom';
import { LogOut } from 'lucide-react';
import clsx from 'clsx';

export const Header = ({ onLogout }: { onLogout?: () => void }) => {
  return (
    <header className="bg-surface-container border-b border-outline-variant w-full sticky top-0 z-50">
      <div className="flex justify-between items-center w-full h-16 px-gutter max-w-[1200px] mx-auto">
        <div className="flex items-center gap-sm">
          <img 
            alt="SecureStego Logo" 
            className="h-8 w-8 object-contain" 
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuBv1YCkc_TUOBFbk-6aam9P3ukmxcaiptv91UxkZuB3L8u7qUs0YN8u8-_vQbmq9CN3sBgoVRTnJbOYouDd6iIcqOUco9fci_PEDN1sJaovPsSULj5jqf5u_llIiPrjJ4HSLEzi5pjaVbZP-lrb1Yfb7ptJsdt-K-MGQPTKlj7Ff-t5whhtbIpui21t3DxfNgHPsOxB10k4RDTGWlf5WcQf7q6xywHW9GsWwny2981nPKKNcRCOmk9lxg"
          />
          <span className="font-headline-sm text-2xl font-bold text-on-surface tracking-tight">
            SecureStego
          </span>
        </div>
        {onLogout && (
          <button 
            onClick={onLogout} 
            className="font-label-code text-[13px] text-on-surface-variant hover:text-primary transition-colors flex items-center gap-xs px-sm py-xs rounded-lg hover:bg-surface-bright duration-150 border border-transparent hover:border-outline-variant"
          >
            Logout <LogOut size={16} />
          </button>
        )}
      </div>
    </header>
  );
};

export const Footer = () => (
  <footer className="bg-surface-container-lowest w-full mt-auto border-t border-surface-container-highest">
    <div className="flex flex-col md:flex-row justify-between items-center w-full py-md px-gutter max-w-[1200px] mx-auto gap-md">
      <span className="font-label-code text-[13px] text-on-surface-variant">
        © 2024 SecureStego. Technical Minimalism for Secure Communications.
      </span>
      <div className="flex items-center gap-md">
        <a className="font-body-sm text-[14px] text-secondary hover:text-primary transition-colors cursor-pointer">Privacy Policy</a>
        <a className="font-body-sm text-[14px] text-secondary hover:text-primary transition-colors cursor-pointer">Terms of Service</a>
        <a className="font-body-sm text-[14px] text-secondary hover:text-primary transition-colors cursor-pointer">API Documentation</a>
      </div>
    </div>
  </footer>
);

export const TabSwitcher = ({ activeTab }: { activeTab: 'encode' | 'decode' }) => {
  const navigate = useNavigate();
  return (
    <div className="bg-surface-container-lowest p-xs rounded-full inline-flex items-center gap-xs mb-lg border border-outline-variant shadow-sm">
      <button 
        onClick={() => navigate('/encode')}
        className={clsx(
          "px-xl py-sm rounded-full font-body-sm text-[14px] transition-all",
          activeTab === 'encode' 
            ? 'bg-surface border border-outline-variant shadow-lg font-semibold text-primary' 
            : 'font-medium text-on-surface-variant hover:text-on-surface'
        )}
      >
        Encode
      </button>
      <button 
        onClick={() => navigate('/decode')}
        className={clsx(
          "px-xl py-sm rounded-full font-body-sm text-[14px] transition-all",
          activeTab === 'decode' 
            ? 'bg-surface border border-outline-variant shadow-lg font-semibold text-primary' 
            : 'font-medium text-on-surface-variant hover:text-on-surface'
        )}
      >
        Decode
      </button>
    </div>
  );
};
