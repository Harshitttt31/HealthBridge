"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { login as apiLogin } from "./api";

const STORAGE_KEY = "healthbridge.auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // auth = { token, role, company_id, username } | null
  const [auth, setAuth] = useState(null);
  // Until we've read localStorage we don't know if the user is logged in.
  const [loading, setLoading] = useState(true);

  // Restore session on first mount (client-only).
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) setAuth(JSON.parse(raw));
    } catch {
      // Corrupt/blocked storage — treat as logged out.
    }
    setLoading(false);
  }, []);

  async function signIn(email, password) {
    const session = await apiLogin(email, password);
    setAuth(session);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    return session;
  }

  function signOut() {
    setAuth(null);
    window.localStorage.removeItem(STORAGE_KEY);
  }

  return (
    <AuthContext.Provider value={{ auth, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth must be used within <AuthProvider>");
  }
  return ctx;
}

// Where each role lands after login.
export function homePathForRole(role) {
  if (role === "hr") return "/dashboard";
  if (role === "provider") return "/dashboard";
  return "/login";
}
