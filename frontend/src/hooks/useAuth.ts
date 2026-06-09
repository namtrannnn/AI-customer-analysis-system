import { useEffect, useState } from "react";
import { getCurrentUser } from "@/services/auth.service";
import type { AuthUser } from "@/types/auth.type";

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const current = getCurrentUser();
    setUser(current);
    setLoading(false);
  }, []);

  const isAuthenticated = !!user;

  return { user, loading, isAuthenticated };
}
