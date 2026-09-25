'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';

type UserRole = 'patient' | 'doctor' | 'admin';

interface User {
  id: number;
  name: string;
  email: string;
  role: UserRole;
}

interface AuthContextType {
  token: string | null;
  user: User | null;
  isLoading: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
};

interface AuthProviderProps {
  children: React.ReactNode;
};

// Check whether a JWT exists and has not expired.
const isTokenValid = (token: string): boolean => {
  try {
    const parts = token.split('.');

    // A JWT must contain header, payload and signature.
    if (parts.length !== 3) {
      return false;
    }

    // Decode the JWT payload.
    const payload = JSON.parse(
      atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'))
    );

    // exp is the expiration time in seconds since Unix epoch.
    if (typeof payload.exp !== 'number') {
      return false;
    }

    const currentTime = Math.floor(Date.now() / 1000);

    return payload.exp > currentTime;
  } catch {
    // Invalid/malformed JWT.
    return false;
  }
};

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    const storedUser = localStorage.getItem('user');

    if (storedToken && storedUser && isTokenValid(storedToken)) {
      try {
        setToken(storedToken);
        setUser(JSON.parse(storedUser));
      } catch {
        // Invalid stored user data.
        localStorage.removeItem('token');
        localStorage.removeItem('user');
      }
    } else {
      // No session or expired/invalid token.
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    }

    setIsLoading(false);
  }, []);

  const login = (token: string, user: User) => {
    setToken(token);
    setUser(user);

    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
  };

  const logout = () => {
    setToken(null);
    setUser(null);

    localStorage.removeItem('token');
    localStorage.removeItem('user');
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};