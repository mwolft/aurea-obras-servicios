"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import {
  getCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
  type AuthCredentials,
  type AuthResult,
  type AuthUser,
  type RegistrationCredentials,
} from "@/lib/api";

type AuthContextValue = {
  user: AuthUser | null;
  isLoading: boolean;
  login: (credentials: AuthCredentials) => Promise<AuthResult>;
  register: (credentials: RegistrationCredentials) => Promise<AuthResult>;
  logout: () => Promise<boolean>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const result = await getCurrentUser();
    setUser(result.status === "success" ? result.user : null);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    let isMounted = true;

    void getCurrentUser().then((result) => {
      if (!isMounted) {
        return;
      }

      setUser(result.status === "success" ? result.user : null);
      setIsLoading(false);
    });

    return () => {
      isMounted = false;
    };
  }, []);

  const login = async (credentials: AuthCredentials) => {
    const result = await loginUser(credentials);
    if (result.status === "success") {
      setUser(result.user);
    }
    return result;
  };

  const register = async (credentials: RegistrationCredentials) => {
    const result = await registerUser(credentials);
    if (result.status === "success") {
      setUser(result.user);
    }
    return result;
  };

  const logout = async () => {
    const result = await logoutUser();
    if (result.status === "success") {
      setUser(null);
      return true;
    }
    return false;
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used within AuthProvider.");
  }

  return value;
}
