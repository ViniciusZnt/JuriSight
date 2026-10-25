"use client";

import { useProfile } from "@/lib/profile";
import { LogoutButton } from "@/components/settings/logout-button";

/** Aba Conta — plano e sessão. Dados pessoais editáveis ficam na aba Perfil. */
export function AccountTab() {
  const { profile } = useProfile();

  return (
    <div className="rounded-xl border border-[#EAEAEF] dark:border-[#26262C] bg-white dark:bg-[#17171B] px-4 py-3.5">
      <p className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "15.5px", fontWeight: 600 }}>
        {profile.name}
      </p>
      <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.8px" }}>
        Plano Pro • em breve
      </p>
      <LogoutButton />
    </div>
  );
}
