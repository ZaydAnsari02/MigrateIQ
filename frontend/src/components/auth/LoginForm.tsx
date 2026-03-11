"use client";

import { useState } from "react";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { authService } from "@/services/authService";

// ─── Lock icon ────────────────────────────────────────────────────────────────

function LockIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <rect x="4" y="9" width="12" height="9" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M7 9V6a3 3 0 016 0v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

// ─── Input field ──────────────────────────────────────────────────────────────

interface InputFieldProps {
  id: string;
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  autoComplete?: string;
  disabled?: boolean;
}

function InputField({ id, label, type, value, onChange, placeholder, autoComplete, disabled }: InputFieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs font-semibold text-zinc-600">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        disabled={disabled}
        className="w-full px-3 py-2.5 text-sm text-zinc-900 bg-white border border-zinc-200 rounded-lg
          placeholder:text-zinc-400
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
          disabled:opacity-50 disabled:cursor-not-allowed
          transition-colors"
      />
    </div>
  );
}

// ─── LoginForm ────────────────────────────────────────────────────────────────

interface LoginFormProps {
  onSuccess: (token: string, username: string) => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState<string | null>(null);
  const [loading, setLoading]   = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password) return;

    setError(null);
    setLoading(true);
    try {
      const { token, username: user } = await authService.login(username.trim(), password);
      onSuccess(token, user);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#F4F5F7] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        {/* Logo / Branding */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-blue-600 text-white mb-4 shadow-lg shadow-blue-200">
            <LockIcon />
          </div>
          <h1 className="text-2xl font-bold text-zinc-900 tracking-tight">MigrateIQ</h1>
          <p className="text-xs text-zinc-400 mt-1">Sign in to your account to continue</p>
        </div>

        {/* Card */}
        <Card>
          <CardBody className="p-6">
            <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>

              <InputField
                id="username"
                label="Username"
                type="text"
                value={username}
                onChange={setUsername}
                placeholder="Enter your username"
                autoComplete="username"
                disabled={loading}
              />

              <InputField
                id="password"
                label="Password"
                type="password"
                value={password}
                onChange={setPassword}
                placeholder="Enter your password"
                autoComplete="current-password"
                disabled={loading}
              />

              {/* Error banner */}
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2.5 text-xs flex items-start gap-2">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="mt-0.5 shrink-0">
                    <circle cx="6" cy="6" r="5.5" stroke="currentColor" strokeWidth="1" />
                    <path d="M6 3.5v3M6 8v.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                  </svg>
                  {error}
                </div>
              )}

              <Button
                type="submit"
                variant="primary"
                size="lg"
                loading={loading}
                disabled={!username.trim() || !password}
                className="w-full mt-1"
              >
                {loading ? "Signing in…" : "Sign in"}
              </Button>

            </form>
          </CardBody>
        </Card>

        <p className="text-center text-[10px] text-zinc-400 mt-6">
          MigrateIQ v1.0.0 · AI-powered BI migration validation
        </p>
      </div>
    </div>
  );
}
