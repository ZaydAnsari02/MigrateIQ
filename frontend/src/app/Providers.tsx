"use client";

import { NotificationsProvider } from "@/context/NotificationsContext";

export function Providers({ children }: { children: React.ReactNode }) {
  return <NotificationsProvider>{children}</NotificationsProvider>;
}
