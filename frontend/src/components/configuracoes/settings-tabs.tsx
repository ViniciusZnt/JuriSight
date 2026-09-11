"use client";

import { useState } from "react";
import { User2, Palette, CreditCard, type LucideIcon } from "lucide-react";
import { ThemeToggle } from "@/components/settings/theme-toggle";
import { ProfileTab } from "@/components/configuracoes/profile-tab";
import { AccountTab } from "@/components/configuracoes/account-tab";

type TabId = "perfil" | "aparencia" | "conta";

const TABS: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: "perfil", label: "Perfil", icon: User2 },
  { id: "aparencia", label: "Aparência", icon: Palette },
  { id: "conta", label: "Conta", icon: CreditCard },
];

/** Abas de Configurações: Perfil (dados pessoais), Aparência (tema) e Conta (plano/sessão). */
export function SettingsTabs() {
  const [active, setActive] = useState<TabId>("perfil");

  return (
    <div>
      <div className="flex items-center gap-1 mb-6 border-b border-[#EAEAEF] dark:border-[#26262C]">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = active === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActive(tab.id)}
              className={`flex items-center gap-1.5 px-3.5 py-2.5 -mb-px border-b-2 transition-colors ${
                isActive
                  ? "border-[#1A3A5C] dark:border-[#8AB0DC] text-[#1A3A5C] dark:text-[#8AB0DC]"
                  : "border-transparent text-[#8A8A9A] dark:text-[#9494A2] hover:text-[#4A4A5A] dark:hover:text-[#C4C4CE]"
              }`}
              style={{ fontSize: "14.4px", fontWeight: isActive ? 600 : 500 }}
            >
              <Icon className="w-3.5 h-3.5" strokeWidth={1.8} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {active === "perfil" && <ProfileTab />}
      {active === "aparencia" && <ThemeToggle />}
      {active === "conta" && <AccountTab />}
    </div>
  );
}
