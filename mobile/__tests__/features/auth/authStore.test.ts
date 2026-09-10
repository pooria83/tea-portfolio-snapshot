import {useAuthStore} from '../../../src/features/auth/authStore';
import {mockUser} from '../../fixtures/user';

const user = mockUser;

const resetState = () =>
  useAuthStore.setState({
    token: null,
    user: null,
    isAuthenticated: false,
    hydrated: false,
    step: 'phone',
    phone: null,
    loading: false,
    error: null,
  });

beforeEach(() => {
  resetState();
});

describe('authStore step machine', () => {
  it('starts in the phone step', () => {
    const state = useAuthStore.getState();
    expect(state.step).toBe('phone');
    expect(state.isAuthenticated).toBe(false);
    expect(state.hydrated).toBe(false);
  });

  it('moves phone → otp after sendOtp', () => {
    const store = useAuthStore.getState();
    store.setPhone('+966501234567');
    store.setLoading(true);
    store.setStep('otp');
    const state = useAuthStore.getState();
    expect(state.phone).toBe('+966501234567');
    expect(state.step).toBe('otp');
    expect(state.loading).toBe(true);
  });

  it('reaches authenticated and clears error on setAuth', () => {
    const store = useAuthStore.getState();
    store.setError('boom');
    store.setAuth('token-1', user);
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.step).toBe('authenticated');
    expect(state.token).toBe('token-1');
    expect(state.user?.id).toBe('user-1');
    expect(state.error).toBeNull();
  });

  it('resets to phone on clearAuth', () => {
    useAuthStore.getState().setAuth('token-1', user);
    useAuthStore.getState().clearAuth();
    const state = useAuthStore.getState();
    expect(state.step).toBe('phone');
    expect(state.phone).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.token).toBeNull();
    expect(state.user).toBeNull();
  });

  it('hydrate restores authenticated session when token+user exist', () => {
    useAuthStore.getState().hydrate('token-1', user);
    const state = useAuthStore.getState();
    expect(state.hydrated).toBe(true);
    expect(state.isAuthenticated).toBe(true);
    expect(state.step).toBe('authenticated');
  });

  it('hydrate with no session stays on phone', () => {
    useAuthStore.getState().hydrate(null, null);
    const state = useAuthStore.getState();
    expect(state.hydrated).toBe(true);
    expect(state.isAuthenticated).toBe(false);
    expect(state.step).toBe('phone');
  });
});
