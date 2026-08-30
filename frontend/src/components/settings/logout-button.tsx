"use client";

import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth";

/** Botão de sair da conta, usado na tela de Configurações. */
export function LogoutButton() {
  const router = useRouter();
  const { logout } = useAuth();

  return (
    <button
      onClick={() => {
        logout();
        router.push("/login");
      }}
      className="flex items-center gap-2 mt-3 px-3.5 py-2 rounded-lg border border-[#E8C2C2] dark:border-[#4A2529] text-[#C44040] dark:text-[#D96B6B] hover:bg-[#FBF0F0] dark:hover:bg-[#2A1517] transition-colors"
      style={{ fontSize: "13.8px", fontWeight: 500 }}
    >
      <LogOut className="w-3.5 h-3.5" strokeWidth={1.8} />
      Sair da conta
    </button>
  );
}
