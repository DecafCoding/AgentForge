import type { ReactNode } from "react";

import { Header } from "./Header";

interface MainLayoutProps {
  children: ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  return (
    <div className="flex flex-col h-screen">
      <Header />
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
