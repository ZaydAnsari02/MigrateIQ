"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LoginForm } from "@/components/auth/LoginForm";
import { useAuth } from "@/hooks";

// ─── Login Page ───────────────────────────────────────────────────────────────

export default function LoginPage() {
  const router = useRouter();
  const { isAuthenticated, initialized, login } = useAuth();

  // Already logged in → go straight to dashboard (wait for initialized first)
  useEffect(() => {
    if (initialized && isAuthenticated) router.replace("/");
  }, [initialized, isAuthenticated, router]);

  function handleSuccess(token: string, username: string) {
    login(token, username);
    router.replace("/");
  }

  return <LoginForm onSuccess={handleSuccess} />;
}
