import {create} from 'zustand';
import type {User} from '../../types/api';

export type AuthStep = 'phone' | 'otp' | 'authenticated';

export interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  hydrated: boolean;
  step: AuthStep;
  phone: string | null;
  loading: boolean;
  error: string | null;
  setStep: (step: AuthStep) => void;
  setPhone: (phone: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearError: () => void;
  setAuth: (token: string, user: User) => void;
  setUser: (user: User) => void;
  clearAuth: () => void;
  hydrate: (token: string | null, user: User | null) => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  hydrated: false,
  step: 'phone',
  phone: null,
  loading: false,
  error: null,
  setStep: (step) => set({step}),
  setPhone: (phone) => set({phone}),
  setLoading: (loading) => set({loading}),
  setError: (error) => set({error}),
  clearError: () => set({error: null}),
  setAuth: (token, user) =>
    set({
      token,
      user,
      isAuthenticated: true,
      hydrated: true,
      step: 'authenticated',
      error: null,
      loading: false,
    }),
  setUser: (user) => set({user}),
  clearAuth: () =>
    set({
      token: null,
      user: null,
      isAuthenticated: false,
      hydrated: true,
      step: 'phone',
      phone: null,
      error: null,
    }),
  hydrate: (token, user) =>
    set({
      token,
      user,
      isAuthenticated: !!token && !!user,
      hydrated: true,
      step: !!token && !!user ? 'authenticated' : 'phone',
    }),
}));
