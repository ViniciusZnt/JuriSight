"use client";

import { useState } from "react";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Sidebar } from "@/components/sidebar";

/** Casca da aplicação: sidebar recolhível (overlay no mobile) + área principal. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#F7F7F9]">
      {/* Overlay no mobile */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-30 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar — estática no desktop, overlay no mobile; some ao recolher */}
      <div
        className={`${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        } md:translate-x-0 fixed md:static inset-y-0 left-0 z-40 overflow-hidden transition-[width,transform] duration-300 ${
          collapsed ? "md:w-0" : "md:w-[260px]"
        }`}
      >
        <Sidebar />
      </div>

      {/* Área principal */}
      <div className="flex flex-col flex-1 min-w-0 relative">
        <button
          onClick={() => {
            if (window.innerWidth < 768) setMobileOpen((v) => !v);
            else setCollapsed((c) => !c);
          }}
          className="absolute top-4 left-4 z-20 flex items-center justify-center w-8 h-8 rounded-lg text-[#9090A0] hover:bg-white hover:text-[#1A3A5C] hover:shadow-[0_1px_4px_rgba(0,0,0,0.08)] transition-all"
          title={collapsed ? "Expandir menu" : "Recolher menu"}
        >
          {collapsed ? (
            <PanelLeftOpen className="w-4 h-4" strokeWidth={1.8} />
          ) : (
            <PanelLeftClose className="w-4 h-4" strokeWidth={1.8} />
          )}
        </button>

        <main className="flex-1 min-h-0 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
