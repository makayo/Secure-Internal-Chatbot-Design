'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { authApi, User, LoginCredentials, RegisterData } from '@/lib/api/auth';
import { ApiError } from '@/lib/api/client';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Mock user for testing - set to true to bypass authentication
const USE_MOCK_AUTH = process.env.NEXT_PUBLIC_USE_MOCK_AUTH === 'true' || process.env.NODE_ENV === 'development';

const MOCK_USER: User = {
  id: 'test-user-123',
  email: 'test@example.com',
  name: 'Test User',
  role: 'admin', // Set to 'admin' for testing admin features
  createdAt: new Date().toISOString(),
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    // In testing mode, automatically set mock user
    if (USE_MOCK_AUTH) {
      setUser(MOCK_USER);
      setLoading(false);
      return;
    }

    try {
      const currentUser = await authApi.getCurrentUser();
      setUser(currentUser);
    } catch (error) {
      setUser(null);
      if (error instanceof ApiError && error.status !== 401) {
        console.error('Failed to fetch user:', error);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async (credentials: LoginCredentials) => {
    // In testing mode, automatically succeed with mock user
    if (USE_MOCK_AUTH) {
      setUser(MOCK_USER);
      return;
    }

    try {
      const response = await authApi.login(credentials);
      setUser(response.user);
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw new Error('Login failed');
    }
  };

  const register = async (data: RegisterData) => {
    // In testing mode, automatically succeed with mock user
    if (USE_MOCK_AUTH) {
      setUser(MOCK_USER);
      return;
    }

    try {
      const response = await authApi.register(data);
      setUser(response.user);
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw new Error('Registration failed');
    }
  };

  const logout = async () => {
    // In testing mode, just clear the user
    if (USE_MOCK_AUTH) {
      setUser(null);
      return;
    }

    try {
      await authApi.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setUser(null);
    }
  };

  const value: AuthContextType = {
    user,
    loading,
    isAuthenticated: !!user,
    isAdmin: user?.role === 'admin',
    login,
    register,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

