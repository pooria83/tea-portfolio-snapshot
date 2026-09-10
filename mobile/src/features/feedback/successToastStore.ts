import {create} from 'zustand';

interface SuccessToastState {
  message: string | null;
  showMessage: (message: string) => void;
  clearMessage: () => void;
}

export const useSuccessToastStore = create<SuccessToastState>()((set) => ({
  message: null,
  showMessage: (message) => set({message}),
  clearMessage: () => set({message: null}),
}));
