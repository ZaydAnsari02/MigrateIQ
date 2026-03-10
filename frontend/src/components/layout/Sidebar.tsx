"use client";

import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "@/constants";
import type { NavItem } from "@/types";
import { useAuth } from "@/hooks";
import { useRouter } from "next/navigation";

// ─── Icons ────────────────────────────────────────────────────────────────────

const ICONS: Record<NavItem, React.ReactNode> = {
  dashboard: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="1" y="1" width="6" height="6" rx="1.5" fill="currentColor" opacity=".9" />
      <rect x="9" y="1" width="6" height="6" rx="1.5" fill="currentColor" opacity=".5" />
      <rect x="1" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity=".5" />
      <rect x="9" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity=".3" />
    </svg>
  ),
  upload: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M8 1v9M5 4l3-3 3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M2 11v2a1 1 0 001 1h10a1 1 0 001-1v-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  runs: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M8 4.5v4l2.5 1.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  ),
  results: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M2 12l3.5-4 3 3L12 5l2 2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  explorer: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="1" y="3" width="6" height="10" rx="1.2" stroke="currentColor" strokeWidth="1.4" />
      <rect x="9" y="3" width="6" height="10" rx="1.2" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  ),
  settings: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M8 1.5v1M8 13.5v1M1.5 8h1M13.5 8h1M3.4 3.4l.7.7M11.9 11.9l.7.7M3.4 12.6l.7-.7M11.9 4.1l.7-.7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  ),
};

// ─── Component ────────────────────────────────────────────────────────────────

interface SidebarProps {
  activeNav: NavItem;
  onNav: (id: NavItem) => void;
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ activeNav, onNav, collapsed, onToggle }: SidebarProps) {
  const { username, logout } = useAuth();
const router = useRouter();

function handleLogout() {
  logout();
  router.replace("/login");
}

const initials =
  username
    ?.split(" ")
    .map(n => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() || "U";
  return (
    <aside
      className={cn(
        "flex flex-col bg-white border-r border-zinc-200 z-20 shrink-0 transition-all duration-300",
        collapsed ? "w-14" : "w-52"
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-zinc-100">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center shrink-0 shadow-sm">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 10L5 6l2.5 2.5L10 4l2 2.5" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="font-bold text-zinc-900 text-sm leading-tight tracking-tight truncate">MigrateIQ</div>
            <div className="text-[9px] text-zinc-400 truncate">AI Validation Platform</div>
          </div>
        )}
        <button
          onClick={onToggle}
          className="ml-auto text-zinc-400 hover:text-zinc-600 transition-colors shrink-0"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path
              d={collapsed ? "M5 3l4 4-4 4" : "M9 3l-4 4 4 4"}
              stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      {/* Nav items */}
      <nav className="flex-1 py-3 px-2 flex flex-col gap-0.5 overflow-y-auto">
        {NAV_ITEMS.map(item => {
          const active = activeNav === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNav(item.id as NavItem)}
              title={collapsed ? item.label : undefined}
              className={cn(
                "flex items-center gap-2.5 px-2.5 py-2 rounded-lg w-full text-left transition-all duration-150",
                active
                  ? "bg-blue-50 text-blue-700 font-semibold"
                  : "text-zinc-500 hover:text-zinc-800 hover:bg-zinc-50"
              )}
            >
              <span className="shrink-0">{ICONS[item.id as NavItem]}</span>
              {!collapsed && <span className="text-xs truncate">{item.label}</span>}
              {!collapsed && active && (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />
              )}
            </button>
          );
        })}
      </nav>

      {/* User footer */}
      <div className={cn("border-t border-zinc-100 p-3", collapsed ? "flex justify-center" : "")}>
        {collapsed ? (
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-400 to-indigo-600 flex items-center justify-center text-white text-[10px] font-bold">
            {initials}
          </div>
        ) : (
          <div className="flex items-center gap-2.5 w-full">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-400 to-indigo-600 flex items-center justify-center text-white text-[10px] font-bold shrink-0">
              {initials}
            </div>

            <div className="min-w-0">
              <div className="text-xs font-medium text-zinc-700 truncate">
                {username || "User"}
              </div>
              <div className="text-[10px] text-zinc-400 truncate">
                Logged in
              </div>
            </div>
           <button
        onClick={handleLogout}
        className="text-zinc-400 hover:text-red-600 transition-colors"
        title="Logout"
      >
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
          <path
            d="M6 3H3.5A1.5 1.5 0 002 4.5v7A1.5 1.5 0 003.5 13H6"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
          <path
            d="M10 11l3-3-3-3M13 8H6"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button> 
          </div>
        )}
      </div>
    </aside>
  );
}
