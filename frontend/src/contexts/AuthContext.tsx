import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { authApi, ApiError } from "../api";

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  needsSetup: boolean;
  username: string | null;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  setupAuth: (username: string, password: string) => Promise<boolean>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [needsSetup, setNeedsSetup] = useState(false);
  const [username, setUsername] = useState<string | null>(null);

  const checkAuth = useCallback(async () => {
    setIsLoading(true);
    try {
      // First check if auth is configured
      const status = await authApi.checkStatus();

      if (!status.configured) {
        setNeedsSetup(true);
        setIsAuthenticated(false);
        setUsername(null);
        return;
      }

      setNeedsSetup(false);

      // Check if we have stored credentials
      const storedAuth = localStorage.getItem("auth");
      if (!storedAuth) {
        setIsAuthenticated(false);
        setUsername(null);
        return;
      }

      // Verify credentials
      try {
        const result = await authApi.verify();
        setIsAuthenticated(true);
        setUsername(result.username);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          localStorage.removeItem("auth");
          setIsAuthenticated(false);
          setUsername(null);
        }
      }
    } catch (error) {
      console.error("Auth check failed:", error);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = async (user: string, password: string): Promise<boolean> => {
    const credentials = btoa(`${user}:${password}`);
    localStorage.setItem("auth", credentials);

    try {
      const result = await authApi.verify();
      setIsAuthenticated(true);
      setUsername(result.username);
      return true;
    } catch (error) {
      localStorage.removeItem("auth");
      setIsAuthenticated(false);
      setUsername(null);
      return false;
    }
  };

  const logout = () => {
    localStorage.removeItem("auth");
    setIsAuthenticated(false);
    setUsername(null);
  };

  const setupAuth = async (
    user: string,
    password: string,
  ): Promise<boolean> => {
    try {
      await authApi.setup(user, password);
      // After setup, log in
      return await login(user, password);
    } catch (error) {
      console.error("Setup failed:", error);
      return false;
    }
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        needsSetup,
        username,
        login,
        logout,
        setupAuth,
        checkAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
