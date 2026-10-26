import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ApiError, api, setCsrfToken, setUnauthorizedHandler } from "../api/client";

export interface User {
  user_id: string;
  role: "user" | "admin";
}

export type AuthState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "error"; error: ApiError }
  | { status: "authenticated"; user: User };

interface AuthContextValue {
  state: AuthState;
  signIn: (subject: string) => Promise<void>;
  signOut: () => Promise<void>;
  retry: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function loadSession(): Promise<User | null> {
  try {
    const user = await api.get<User>("/api/v1/auth/me");
    const { csrf_token } = await api.get<{ csrf_token: string }>("/api/v1/auth/csrf");
    setCsrfToken(csrf_token);
    return user;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const queryClient = useQueryClient();

  const load = useCallback(() => {
    loadSession().then(
      (user) => setState(user ? { status: "authenticated", user } : { status: "anonymous" }),
      (error: unknown) =>
        setState({
          status: "error",
          error: error instanceof ApiError ? error : new ApiError(0, "network_error"),
        }),
    );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const retry = useCallback(() => {
    setState({ status: "loading" });
    load();
  }, [load]);

  useEffect(() => {
    // The server ended the session: forget everything that belonged to it.
    setUnauthorizedHandler(() => {
      setCsrfToken(null);
      queryClient.clear();
      setState({ status: "anonymous" });
    });
    return () => setUnauthorizedHandler(null);
  }, [queryClient]);

  const signIn = useCallback(async (subject: string) => {
    const { csrf_token } = await api.post<{ user_id: string; csrf_token: string }>(
      "/api/v1/auth/dev-login",
      { subject },
    );
    setCsrfToken(csrf_token);
    const user = await api.get<User>("/api/v1/auth/me");
    setState({ status: "authenticated", user });
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.post("/api/v1/auth/logout");
    } finally {
      // Whatever the server said, this browser must stop acting as the user.
      setCsrfToken(null);
      queryClient.clear();
      setState({ status: "anonymous" });
    }
  }, [queryClient]);

  const value = useMemo(
    () => ({ state, signIn, signOut, retry }),
    [state, signIn, signOut, retry],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
