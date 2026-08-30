import { SettingsTabs } from "@/components/configuracoes/settings-tabs";

/** Configurações — Perfil, Aparência e Conta. */
export default function ConfiguracoesPage() {
  return (
    <div className="min-h-full bg-[#F7F7F9] dark:bg-[#0E0E11]">
      <header className="pl-20 pr-8 py-4">
        <h1 className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "20.7px", fontWeight: 600 }}>
          Configurações
        </h1>
      </header>

      <div className="mx-auto max-w-2xl px-4 sm:px-8 pb-12">
        <SettingsTabs />
      </div>
    </div>
  );
}
