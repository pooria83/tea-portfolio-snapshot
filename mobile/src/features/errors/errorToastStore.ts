import {create} from 'zustand';

interface ErrorToastState {
  error: unknown;
  showError: (error: unknown) => void;
  clearError: () => void;
}

export const useErrorToastStore = create<ErrorToastState>()((set) => ({
  error: null,
  showError: (error) => set({error}),
  clearError: () => set({error: null}),
}));
