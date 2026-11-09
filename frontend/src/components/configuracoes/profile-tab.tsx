"use client";

import { useEffect, useState } from "react";
import { Check, User2 } from "lucide-react";
import { useProfile, initialsOf, type Role } from "@/lib/profile";

const ROLES: Role[] = ["Advogado", "Assistente Jurídica"];

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  readOnly = false,
  hint,
}: {
  label: string;
  value: string;
  onChange?: (v: string) => void;
  placeholder?: string;
  type?: string;
  readOnly?: boolean;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="block mb-1.5 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
        {label}
      </span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        placeholder={placeholder}
        readOnly={readOnly}
        className={`w-full px-3 py-2.5 rounded-xl border border-[#E4E4EC] dark:border-[#2A2A32] bg-[#FAFAFA] dark:bg-[#1C1C21] text-[#0F1117] dark:text-[#ECECEF] placeholder:text-[#C0C0CE] dark:placeholder:text-[#4A4A54] outline-none focus:border-[#1A3A5C] dark:focus:border-[#8AB0DC] focus:ring-2 focus:ring-[#1A3A5C]/10 dark:focus:ring-[#8AB0DC]/10 transition-all${readOnly ? " cursor-default text-[#6B6B80] dark:text-[#A6A6B4]" : ""}`}
        style={{ fontSize: "14.9px" }}
      />
      {hint && (
        <span className="block mt-1 text-[#AEAEBF] dark:text-[#6E6E7C]" style={{ fontSize: "12.1px" }}>
          {hint}
        </span>
      )}
    </label>
  );
}

/** Aba Perfil — nome e e-mail da conta (só leitura) e telefone, OAB e papel, gravados na conta
 *  via useProfile (PATCH /auth/me/perfil). */
export function ProfileTab() {
  const { profile, hydrated, update } = useProfile();
  const extras = { phone: profile.phone, oab: profile.oab, role: profile.role };
  const [draft, setDraft] = useState(extras);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // O usuário da sessão chega depois do primeiro render, então o valor inicial acima pode ter
  // capturado o padrão antes do perfil real chegar — sincroniza aqui.
  useEffect(() => {
    if (hydrated) setDraft(extras);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated]);

  const dirty = JSON.stringify(draft) !== JSON.stringify(extras);

  const set = <K extends keyof typeof draft>(key: K) => (v: (typeof draft)[K]) =>
    setDraft((prev) => ({ ...prev, [key]: v }));

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dirty || saving) return;
    setSaving(true);
    setErro(null);
    try {
      await update(draft);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível salvar o perfil. Tente de novo.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={handleSave} className="rounded-xl border border-[#EAEAEF] dark:border-[#26262C] bg-white dark:bg-[#17171B] p-5">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-12 h-12 rounded-full bg-[#E8EDF4] dark:bg-[#1E2A38] flex items-center justify-center flex-shrink-0">
            <span className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "16.7px", fontWeight: 600 }}>
              {initialsOf(profile.name)}
            </span>
          </div>
          <div className="flex items-center gap-2 text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "12.6px" }}>
            <User2 className="w-3.5 h-3.5" strokeWidth={1.8} />
            Iniciais geradas a partir do nome
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Nome" value={profile.name} readOnly hint="Vem da sua conta" />
          <Field label="E-mail" type="email" value={profile.email} readOnly hint="Vem da sua conta" />
          <Field label="Telefone" type="tel" value={draft.phone} onChange={set("phone")} placeholder="(48) 99999-0000" />
          <Field label="Número da OAB" value={draft.oab} onChange={set("oab")} placeholder="Ex: 123456/SC" />
        </div>

        <label className="block mt-4">
          <span className="block mb-1.5 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
            Papel
          </span>
          <div className="flex gap-2">
            {ROLES.map((role) => (
              <button
                key={role}
                type="button"
                onClick={() => set("role")(role)}
                className={`flex-1 px-3 py-2.5 rounded-xl border transition-all ${
                  draft.role === role
                    ? "bg-[#EFF4FA] dark:bg-[#1A2A3C] border-[#1A3A5C] dark:border-[#8AB0DC] text-[#1A3A5C] dark:text-[#8AB0DC]"
                    : "bg-[#FAFAFA] dark:bg-[#1C1C21] border-[#E4E4EC] dark:border-[#2A2A32] text-[#6B6B80] dark:text-[#A6A6B4] hover:border-[#1A3A5C]/30 dark:hover:border-[#8AB0DC]/30"
                }`}
                style={{ fontSize: "13.8px", fontWeight: draft.role === role ? 600 : 400 }}
              >
                {role}
              </button>
            ))}
          </div>
        </label>

        <div className="flex items-center justify-end gap-3 mt-5 pt-4 border-t border-[#F0F0F6] dark:border-[#26262C]">
          {erro && (
            <span role="alert" className="text-[#A1362F] dark:text-[#F0938B]" style={{ fontSize: "13.2px" }}>
              {erro}
            </span>
          )}
          {saved && (
            <span className="flex items-center gap-1.5 text-[#1E6B4A] dark:text-[#6FCB9A]" style={{ fontSize: "13.2px" }}>
              <Check className="w-3.5 h-3.5" strokeWidth={2.5} />
              Salvo
            </span>
          )}
          <button
            type="submit"
            disabled={!dirty || saving}
            className={`px-4 py-2 rounded-xl transition-all ${
              dirty
                ? "bg-[#1A3A5C] hover:bg-[#1E4570] text-white shadow-[0_2px_10px_rgba(26,58,92,0.24)] active:scale-[0.98]"
                : "bg-[#F0F0F4] dark:bg-[#1C1C21] text-[#C0C0D0] dark:text-[#4A4A54] cursor-not-allowed"
            }`}
            style={{ fontSize: "14.4px", fontWeight: 600 }}
          >
            {saving ? "Salvando…" : "Salvar alterações"}
          </button>
        </div>
      </form>

    </div>
  );
}
