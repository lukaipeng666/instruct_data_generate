import { create } from 'zustand';

interface AuthState {
  token: string | null;
  username: string | null;
  isAdmin: boolean;
  setAuth: (token: string, username: string, isAdmin: boolean) => void;
  clearAuth: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()((set, get) => {
  // 从localStorage初始化
  const storedToken = localStorage.getItem('access_token');
  const storedUsername = localStorage.getItem('username');
  const storedIsAdmin = localStorage.getItem('is_admin') === 'true';
  
  return {
    token: storedToken,
    username: storedUsername,
    isAdmin: storedIsAdmin,
    setAuth: (token, username, isAdmin) => {
      localStorage.setItem('access_token', token);
      localStorage.setItem('username', username);
      localStorage.setItem('is_admin', String(isAdmin));
      set({ token, username, isAdmin });
    },
    clearAuth: () => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('username');
      localStorage.removeItem('is_admin');
      set({ token: null, username: null, isAdmin: false });
    },
    isAuthenticated: () => !!get().token,
  };
});

