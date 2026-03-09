"use client";

import { cn } from "@/lib/utils";

interface HeaderProps {
  className?: string;
}

export function Header({ className }: HeaderProps) {
  const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <header
      className={cn(
        "bg-white border-b border-zinc-200 px-6 py-3.5 flex items-center gap-4 shrink-0",
        className
      )}
    >
      {/* Brand */}
      <div>
        <div className="flex items-center gap-2">
          <h1 className="font-bold text-zinc-900 text-base tracking-tight">MigrateIQ</h1>
          <span className="px-2 py-0.5 text-[10px] font-bold bg-blue-600 text-white rounded-md tracking-widest uppercase">
            AI
          </span>
        </div>
        <p className="text-xs text-zinc-400 mt-0.5">
          AI-powered BI Migration Validation · Tableau → Power BI
        </p>
      </div>

      {/* Right actions */}
      <div className="ml-auto flex items-center gap-3">
        {/* Live indicator */}
        <div className="flex items-center gap-1.5 bg-emerald-50 border border-emerald-200 text-emerald-700 px-3 py-1.5 rounded-lg text-xs font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          Validation Engine Active
        </div>

        {/* Clock */}
        <div className="hidden md:flex items-center gap-1.5 text-xs text-zinc-400 font-mono bg-zinc-50 border border-zinc-200 px-3 py-1.5 rounded-lg">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.2" />
            <path d="M6 3.5v3l1.5 1" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
          {now}
        </div>

        {/* Notifications */}
        <button className="w-8 h-8 rounded-lg border border-zinc-200 flex items-center justify-center text-zinc-500 hover:bg-zinc-50 transition-colors relative">
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
            <path d="M7.5 2a5 5 0 015 5v2.5l1 1.5H1.5L2.5 9.5V7a5 5 0 015-5zM6 11.5a1.5 1.5 0 003 0" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-red-500" />
        </button>

        {/* Settings */}
        <button className="w-8 h-8 rounded-lg border border-zinc-200 flex items-center justify-center text-zinc-500 hover:bg-zinc-50 transition-colors">
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
            <circle cx="7.5" cy="7.5" r="2" stroke="currentColor" strokeWidth="1.3" />
            <path d="M7.5 1v1.5M7.5 12.5V14M1 7.5h1.5M12.5 7.5H14M3.2 3.2l1 1M10.8 10.8l1 1M3.2 11.8l1-1M10.8 4.2l1-1" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
        </button>
      </div>
    </header>
  );
}
