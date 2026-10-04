let token: string | null = null;

export const setToken = (newToken: string | null) => {
  token = newToken;
};

export const getToken = () => token;

// Helper to manage auth headers
const authHeaders = (): Record<string, string> => {
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
};

// Error handling wrapper
const handleResponse = async (res: Response) => {
  if (!res.ok) {
    let errorMsg = 'An error occurred';
    try {
      const data = await res.json();
      if (Array.isArray(data.detail)) {
        errorMsg = data.detail.map((e: any) => e.msg).join(', ');
      } else if (typeof data.detail === 'string') {
        errorMsg = data.detail;
      } else if (data.detail) {
        errorMsg = JSON.stringify(data.detail);
      }
    } catch {
      errorMsg = res.statusText;
    }
    throw new Error(errorMsg);
  }
  return res.json();
};

export const api = {
  login: async (formData: URLSearchParams) => {
    // URLSearchParams creates the correct application/x-www-form-urlencoded format
    const res = await fetch('/auth/login', {
      method: 'POST',
      body: formData,
    });
    return handleResponse(res);
  },

  register: async (data: Record<string, any>) => {
    const res = await fetch('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse(res);
  },

  searchUsers: async (query: string) => {
    const res = await fetch(`/auth/users?q=${encodeURIComponent(query)}`, {
      headers: authHeaders(),
    });
    return handleResponse(res);
  },

  getRecentOperations: async () => {
    const res = await fetch('/operations/recent', {
      headers: authHeaders(),
    });
    return handleResponse(res);
  },

  encode: async (formData: FormData) => {
    const res = await fetch('/encode', {
      method: 'POST',
      headers: authHeaders(),
      body: formData, // Browser sets Content-Type to multipart/form-data with boundary automatically
    });
    return handleResponse(res);
  },

  decode: async (formData: FormData) => {
    const res = await fetch('/decode', {
      method: 'POST',
      headers: authHeaders(),
      body: formData,
    });
    return handleResponse(res);
  },

  downloadFile: async (url: string) => {
    const res = await fetch(url, { headers: authHeaders() });
    if (!res.ok) {
        let msg = "Download failed";
        try { const data = await res.json(); msg = data.detail || msg; } catch {}
        throw new Error(msg);
    }
    const blob = await res.blob();
    
    // Extract filename from Content-Disposition if present
    let filename = 'stego_image.png';
    const disposition = res.headers.get('Content-Disposition');
    if (disposition && disposition.indexOf('attachment') !== -1) {
        const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
        const matches = filenameRegex.exec(disposition);
        if (matches != null && matches[1]) filename = matches[1].replace(/['"]/g, '');
    }

    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(objectUrl);
  }
};
