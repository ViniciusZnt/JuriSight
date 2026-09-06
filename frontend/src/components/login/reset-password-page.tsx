"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Lock, ArrowRight, CheckCircle2 } from "lucide-react";

/** Redefinir senha — fora do escopo do RFC. Mockado: em produção o link do e-mail traria um
 *  token na URL que seria validado aqui; sem backend, o formulário só valida os campos. */
export function ResetPasswordPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const passwordTooShort = password.length > 0 && password.length < 6;
  const passwordsMismatch = confirmPassword.length > 0 && password !== confirmPassword;
  const canSubmit = password.length >= 6 && confirmPassword === password && !loading;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      setDone(true);
    }, 500);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F7F7F9] dark:bg-[#0E0E11] p-6">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo.png"
            alt="JuriSight"
            className="w-12 h-12 object-contain select-none mb-3 dark:brightness-0 dark:invert"
            draggable={false}
          />
          <h1 className="text-[#0F1117] dark:text-[#ECECEF] tracking-[-0.02em]" style={{ fontSize: "22.4px", fontWeight: 600 }}>
            Redefinir senha
          </h1>
          <p className="text-[#8A8A9A] dark:text-[#9494A2] mt-1 text-center" style={{ fontSize: "13.8px" }}>
            Escolha uma nova senha para sua conta
          </p>
        </div>

        <div className="rounded-2xl border border-[#E4E4EC] dark:border-[#26262C] bg-white dark:bg-[#17171B] p-6 shadow-[0_4px_32px_rgba(0,0,0,0.07)] dark:shadow-none">
          {done ? (
            <div className="flex flex-col items-center text-center py-2">
              <div className="w-12 h-12 rounded-xl bg-[#EDF7F2] dark:bg-[#122A1E] flex items-center justify-center mb-4">
                <CheckCircle2 className="w-5 h-5 text-[#1E6B4A] dark:text-[#6FCB9A]" strokeWidth={1.8} />
              </div>
              <p className="text-[#0F1117] dark:text-[#ECECEF] mb-1.5" style={{ fontSize: "15.5px", fontWeight: 600 }}>
                Senha redefinida
              </p>
              <p className="text-[#8A8A9A] dark:text-[#9494A2] leading-relaxed mb-5" style={{ fontSize: "13.8px" }}>
                Sua senha foi alterada com sucesso. Entre com a nova senha.
              </p>
              <button
                type="button"
                onClick={() => router.push("/login")}
                className="flex w-full items-center justify-center gap-2 rounded-xl py-2.5 bg-[#1A3A5C] hover:bg-[#1E4570] text-white shadow-[0_2px_14px_rgba(26,58,92,0.30)] active:scale-[0.98] transition-all"
                style={{ fontSize: "15.5px", fontWeight: 600 }}
              >
                Ir para o login
                <ArrowRight className="w-4 h-4" strokeWidth={2} />
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <div className="mb-4">
                <label className="block mb-1.5 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
                  Nova senha
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#AEAEBF] dark:text-[#6E6E7C]" strokeWidth={1.8} />
                  <input
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    autoFocus
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Mínimo 6 caracteres"
                    className={`w-full pl-9 pr-9 py-2.5 rounded-xl border bg-[#FAFAFA] dark:bg-[#1C1C21] text-[#0F1117] dark:text-[#ECECEF] placeholder:text-[#C0C0CE] dark:placeholder:text-[#4A4A54] outline-none focus:ring-2 transition-all ${
                      passwordTooShort
                        ? "border-[#C44040] dark:border-[#D96B6B] focus:border-[#C44040] dark:focus:border-[#D96B6B] focus:ring-[#C44040]/10 dark:focus:ring-[#D96B6B]/10"
                        : "border-[#E4E4EC] dark:border-[#2A2A32] focus:border-[#1A3A5C] dark:focus:border-[#8AB0DC] focus:ring-[#1A3A5C]/10 dark:focus:ring-[#8AB0DC]/10"
                    }`}
                    style={{ fontSize: "14.9px" }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#AEAEBF] dark:text-[#6E6E7C] hover:text-[#4A4A5A] dark:hover:text-[#C4C4CE] transition-colors"
                    title={showPassword ? "Ocultar senha" : "Mostrar senha"}
                    aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                    aria-pressed={showPassword}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" strokeWidth={1.8} /> : <Eye className="w-4 h-4" strokeWidth={1.8} />}
                  </button>
                </div>
                {passwordTooShort && (
                  <p className="mt-1.5 text-[#C44040] dark:text-[#D96B6B]" style={{ fontSize: "12.1px" }}>
                    A senha precisa ter pelo menos 6 caracteres.
                  </p>
                )}
              </div>

              <div className="mb-2">
                <label className="block mb-1.5 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
                  Confirmar nova senha
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#AEAEBF] dark:text-[#6E6E7C]" strokeWidth={1.8} />
                  <input
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repita a nova senha"
                    className={`w-full pl-9 pr-3 py-2.5 rounded-xl border bg-[#FAFAFA] dark:bg-[#1C1C21] text-[#0F1117] dark:text-[#ECECEF] placeholder:text-[#C0C0CE] dark:placeholder:text-[#4A4A54] outline-none focus:ring-2 transition-all ${
                      passwordsMismatch
                        ? "border-[#C44040] dark:border-[#D96B6B] focus:border-[#C44040] dark:focus:border-[#D96B6B] focus:ring-[#C44040]/10 dark:focus:ring-[#D96B6B]/10"
                        : "border-[#E4E4EC] dark:border-[#2A2A32] focus:border-[#1A3A5C] dark:focus:border-[#8AB0DC] focus:ring-[#1A3A5C]/10 dark:focus:ring-[#8AB0DC]/10"
                    }`}
                    style={{ fontSize: "14.9px" }}
                  />
                </div>
                {passwordsMismatch && (
                  <p className="mt-1.5 text-[#C44040] dark:text-[#D96B6B]" style={{ fontSize: "12.1px" }}>
                    As senhas não coincidem.
                  </p>
                )}
              </div>

              <button
                type="submit"
                disabled={!canSubmit}
                className={`mt-5 flex w-full items-center justify-center gap-2 rounded-xl py-2.5 transition-all ${
                  canSubmit
                    ? "bg-[#1A3A5C] hover:bg-[#1E4570] text-white shadow-[0_2px_14px_rgba(26,58,92,0.30)] active:scale-[0.98]"
                    : "bg-[#F0F0F4] dark:bg-[#1C1C21] text-[#C0C0D0] dark:text-[#4A4A54] cursor-not-allowed"
                }`}
                style={{ fontSize: "15.5px", fontWeight: 600 }}
              >
                {loading ? "Salvando…" : "Redefinir senha"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
