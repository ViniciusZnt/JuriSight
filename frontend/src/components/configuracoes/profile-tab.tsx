"use client";

import { useEffect, useState } from "react";
import { Check, Eye, EyeOff, Lock, User2 } from "lucide-react";
import { useProfile, initialsOf, type Role } from "@/lib/profile";

const ROLES: Role[] = ["Advogado", "Assistente Jurídica"];

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <label className="block">
      <span className="block mb-1.5 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
        {label}
      </span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2.5 rounded-xl border border-[#E4E4EC] dark:border-[#2A2A32] bg-[#FAFAFA] dark:bg-[#1C1C21] text-[#0F1117] dark:text-[#ECECEF] placeholder:text-[#C0C0CE] dark:placeholder:text-[#4A4A54] outline-none focus:border-[#1A3A5C] dark:focus:border-[#8AB0DC] focus:ring-2 focus:ring-[#1A3A5C]/10 dark:focus:ring-[#8AB0DC]/10 transition-all"
        style={{ fontSize: "14.9px" }}
      />
    </label>
  );
}

/** Aba Perfil — dados pessoais editáveis (nome, e-mail, telefone, OAB, papel) e troca de senha.
 *  Sem backend: persiste em localStorage via useProfile; a troca de senha é apenas ilustrativa. */
export function ProfileTab() {
  const { profile, hydrated, update } = useProfile();
  const [draft, setDraft] = useState(profile);
  const [saved, setSaved] = useState(false);

  // O provider hidrata a partir do localStorage num efeito (depois do primeiro render), então o
  // valor inicial acima pode ter capturado o padrão antes do perfil real chegar — sincroniza aqui.
  useEffect(() => {
    if (hydrated) setDraft(profile);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated]);

  const dirty = JSON.stringify(draft) !== JSON.stringify(profile);

  const set = <K extends keyof typeof draft>(key: K) => (v: (typeof draft)[K]) =>
    setDraft((prev) => ({ ...prev, [key]: v }));

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!dirty) return;
    update(draft);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  // Troca de senha — sem backend de auth, é apenas ilustrativa (não há senha real para validar).
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [passwordSaved, setPasswordSaved] = useState(false);
  const passwordsMismatch = confirmPassword.length > 0 && newPassword !== confirmPassword;
  const canUpdatePassword = newPassword.length >= 6 && newPassword === confirmPassword;

  const handlePasswordUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canUpdatePassword) return;
    setNewPassword("");
    setConfirmPassword("");
    setPasswordSaved(true);
    setTimeout(() => setPasswordSaved(false), 2000);
  };

  return (
    <div className="space-y-6">
      <form onSubmit={handleSave} className="rounded-xl border border-[#EAEAEF] dark:border-[#26262C] bg-white dark:bg-[#17171B] p-5">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-12 h-12 rounded-full bg-[#E8EDF4] dark:bg-[#1E2A38] flex items-center justify-center flex-shrink-0">
            <span className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "16.7px", fontWeight: 600 }}>
              {initialsOf(draft.name)}
            </span>
          </div>
          <div className="flex items-center gap-2 text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "12.6px" }}>
            <User2 className="w-3.5 h-3.5" strokeWidth={1.8} />
            Iniciais geradas a partir do nome
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Nome completo" value={draft.name} onChange={set("name")} placeholder="Seu nome" />
          <Field label="E-mail" type="email" value={draft.email} onChange={set("email")} placeholder="voce@escritorio.com.br" />
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
          {saved && (
            <span className="flex items-center gap-1.5 text-[#1E6B4A] dark:text-[#6FCB9A]" style={{ fontSize: "13.2px" }}>
              <Check className="w-3.5 h-3.5" strokeWidth={2.5} />
              Salvo
            </span>
          )}
          <button
            type="submit"
            disabled={!dirty}
            className={`px-4 py-2 rounded-xl transition-all ${
              dirty
                ? "bg-[#1A3A5C] hover:bg-[#1E4570] text-white shadow-[0_2px_10px_rgba(26,58,92,0.24)] active:scale-[0.98]"
                : "bg-[#F0F0F4] dark:bg-[#1C1C21] text-[#C0C0D0] dark:text-[#4A4A54] cursor-not-allowed"
            }`}
            style={{ fontSize: "14.4px", fontWeight: 600 }}
          >
            Salvar alterações
          </button>
        </div>
      </form>

      <form onSubmit={handlePasswordUpdate} className="rounded-xl border border-[#EAEAEF] dark:border-[#26262C] bg-white dark:bg-[#17171B] p-5">
        <p className="text-[#0F1117] dark:text-[#ECECEF] mb-4" style={{ fontSize: "15.5px", fontWeight: 600 }}>
          Alterar senha
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="block">
            <span className="block mb-1.5 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
              Nova senha
            </span>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#AEAEBF] dark:text-[#6E6E7C]" strokeWidth={1.8} />
              <input
                type={showPassword ? "text" : "password"}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Mínimo 6 caracteres"
                className="w-full pl-9 pr-9 py-2.5 rounded-xl border border-[#E4E4EC] dark:border-[#2A2A32] bg-[#FAFAFA] dark:bg-[#1C1C21] text-[#0F1117] dark:text-[#ECECEF] placeholder:text-[#C0C0CE] dark:placeholder:text-[#4A4A54] outline-none focus:border-[#1A3A5C] dark:focus:border-[#8AB0DC] focus:ring-2 focus:ring-[#1A3A5C]/10 dark:focus:ring-[#8AB0DC]/10 transition-all"
                style={{ fontSize: "14.9px" }}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#AEAEBF] dark:text-[#6E6E7C] hover:text-[#4A4A5A] dark:hover:text-[#C4C4CE] transition-colors"
              >
                {showPassword ? <EyeOff className="w-4 h-4" strokeWidth={1.8} /> : <Eye className="w-4 h-4" strokeWidth={1.8} />}
              </button>
            </div>
          </label>

          <label className="block">
            <span className="block mb-1.5 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
              Confirmar nova senha
            </span>
            <input
              type={showPassword ? "text" : "password"}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Repita a nova senha"
              className={`w-full px-3 py-2.5 rounded-xl border bg-[#FAFAFA] dark:bg-[#1C1C21] text-[#0F1117] dark:text-[#ECECEF] placeholder:text-[#C0C0CE] dark:placeholder:text-[#4A4A54] outline-none focus:ring-2 transition-all ${
                passwordsMismatch
                  ? "border-[#C44040] dark:border-[#D96B6B] focus:border-[#C44040] dark:focus:border-[#D96B6B] focus:ring-[#C44040]/10 dark:focus:ring-[#D96B6B]/10"
                  : "border-[#E4E4EC] dark:border-[#2A2A32] focus:border-[#1A3A5C] dark:focus:border-[#8AB0DC] focus:ring-[#1A3A5C]/10 dark:focus:ring-[#8AB0DC]/10"
              }`}
              style={{ fontSize: "14.9px" }}
            />
          </label>
        </div>
        {passwordsMismatch && (
          <p className="mt-1.5 text-[#C44040] dark:text-[#D96B6B]" style={{ fontSize: "12.1px" }}>
            As senhas não coincidem.
          </p>
        )}

        <div className="flex items-center justify-end gap-3 mt-4 pt-4 border-t border-[#F0F0F6] dark:border-[#26262C]">
          {passwordSaved && (
            <span className="flex items-center gap-1.5 text-[#1E6B4A] dark:text-[#6FCB9A]" style={{ fontSize: "13.2px" }}>
              <Check className="w-3.5 h-3.5" strokeWidth={2.5} />
              Senha atualizada
            </span>
          )}
          <button
            type="submit"
            disabled={!canUpdatePassword}
            className={`px-4 py-2 rounded-xl transition-all ${
              canUpdatePassword
                ? "bg-[#1A3A5C] hover:bg-[#1E4570] text-white shadow-[0_2px_10px_rgba(26,58,92,0.24)] active:scale-[0.98]"
                : "bg-[#F0F0F4] dark:bg-[#1C1C21] text-[#C0C0D0] dark:text-[#4A4A54] cursor-not-allowed"
            }`}
            style={{ fontSize: "14.4px", fontWeight: 600 }}
          >
            Atualizar senha
          </button>
        </div>
      </form>
    </div>
  );
}
