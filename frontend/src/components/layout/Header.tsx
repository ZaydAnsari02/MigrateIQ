"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useNotifications } from "@/context/NotificationsContext";
import type { Notification, NotifType } from "@/context/NotificationsContext";

// ─── Type icon ────────────────────────────────────────────────────────────────

function TypeIcon({ type }: { type: NotifType }) {
  if (type === "success") return (
    <span className="w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
      <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
        <path d="M2 5.5l2.5 2.5 4.5-5" stroke="#059669" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
  if (type === "error") return (
    <span className="w-6 h-6 rounded-full bg-red-100 flex items-center justify-center shrink-0">
      <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
        <path d="M2.5 2.5l6 6M8.5 2.5l-6 6" stroke="#dc2626" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </span>
  );
  if (type === "warning") return (
    <span className="w-6 h-6 rounded-full bg-amber-100 flex items-center justify-center shrink-0">
      <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
        <path d="M5.5 2v4M5.5 8v.5" stroke="#d97706" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </span>
  );
  return (
    <span className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
      <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
        <path d="M5.5 5v3M5.5 3v.5" stroke="#2563eb" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="5.5" cy="5.5" r="4.5" stroke="#2563eb" strokeWidth="1" />
      </svg>
    </span>
  );
}

// ─── Relative time ────────────────────────────────────────────────────────────

function relativeTime(date: Date): string {
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// ─── Notification row ─────────────────────────────────────────────────────────

function NotifRow({ notif, onDismiss }: { notif: Notification; onDismiss: (id: string) => void }) {
  return (
    <div className={cn(
      "flex items-start gap-2.5 px-4 py-3 border-b border-zinc-50 last:border-0 transition-colors",
      !notif.read && "bg-blue-50/40"
    )}>
      <TypeIcon type={notif.type} />
      <div className="flex-1 min-w-0">
        <p className={cn("text-xs leading-snug truncate", notif.read ? "text-zinc-600" : "text-zinc-800 font-medium")}>
          {notif.title}
        </p>
        {notif.message && (
          <p className="text-[10px] text-zinc-400 mt-0.5 line-clamp-2">{notif.message}</p>
        )}
        <p className="text-[9px] text-zinc-300 mt-1">{relativeTime(notif.timestamp)}</p>
      </div>
      <button
        onClick={() => onDismiss(notif.id)}
        className="text-zinc-300 hover:text-zinc-500 transition-colors shrink-0 mt-0.5"
      >
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M1.5 1.5l7 7M8.5 1.5l-7 7" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  );
}

// ─── Header ───────────────────────────────────────────────────────────────────

interface HeaderProps {
  className?: string;
}

export function Header({ className }: HeaderProps) {
  const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const { notifications, markAllRead, dismiss, clearAll } = useNotifications();
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const unread = notifications.filter(n => !n.read).length;

  // Close dropdown on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleOpen = () => {
    setOpen(prev => !prev);
    if (!open && unread > 0) markAllRead();
  };

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
        <div className="relative" ref={panelRef}>
          <button
            onClick={handleOpen}
            className="w-8 h-8 rounded-lg border border-zinc-200 flex items-center justify-center text-zinc-500 hover:bg-zinc-50 transition-colors relative"
          >
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
              <path d="M7.5 2a5 5 0 015 5v2.5l1 1.5H1.5L2.5 9.5V7a5 5 0 015-5zM6 11.5a1.5 1.5 0 003 0" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {unread > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center">
                {unread > 9 ? "9+" : unread}
              </span>
            )}
            {unread === 0 && notifications.length > 0 && (
              <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-zinc-300" />
            )}
          </button>

          {/* Dropdown panel */}
          {open && (
            <div className="absolute right-0 top-10 w-80 bg-white border border-zinc-200 rounded-xl shadow-xl z-50 overflow-hidden">
              {/* Panel header */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100">
                <span className="text-xs font-semibold text-zinc-800">
                  Notifications
                  {unread > 0 && (
                    <span className="ml-1.5 px-1.5 py-0.5 bg-blue-100 text-blue-700 text-[9px] font-bold rounded-full">
                      {unread} new
                    </span>
                  )}
                </span>
                {notifications.length > 0 && (
                  <button
                    onClick={clearAll}
                    className="text-[10px] text-zinc-400 hover:text-zinc-600 transition-colors"
                  >
                    Clear all
                  </button>
                )}
              </div>

              {/* Notification list */}
              <div className="max-h-80 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="py-10 text-center">
                    <p className="text-xs text-zinc-400">No notifications yet</p>
                    <p className="text-[10px] text-zinc-300 mt-1">Events will appear here as you work</p>
                  </div>
                ) : (
                  notifications.map(n => (
                    <NotifRow key={n.id} notif={n} onDismiss={dismiss} />
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
