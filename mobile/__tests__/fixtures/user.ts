import type {User} from '../../src/types/api';

export const mockUser: User = {
  id: 'user-1',
  email: 'user@example.com',
  phone: '+965501234567',
  username: 'testuser',
  full_name: 'Test User',
  role: 'seller',
  is_active: true,
  avatar_url: null,
  address: null,
  location_lat: null,
  location_lng: null,
  preferred_language: 'en',
  has_google: false,
  created_at: '2026-01-01T00:00:00Z',
};
