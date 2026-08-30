"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Lock, Mail, ArrowRight } from "lucide-react";
import { useAuth } from "@/lib/auth";

/** Login — fora do escopo do RFC (que não define autenticação/contas). Fluxo mockado: qualquer
 *  e-mail + senha preenchidos entra, sem backend de auth real. */
export function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const canSubmit = email.trim().length > 0 && password.length > 0 && !loading;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setTimeout(() => {
      login();
      router.push("/");
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
            JuriSight
          </h1>
          <p className="text-[#8A8A9A] dark:text-[#9494A2] mt-1" style={{ fontSize: "13.8px" }}>
            Pesquisa contextual de jurisprudência trabalhista
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-[#E4E4EC] dark:border-[#26262C] bg-white dark:bg-[#17171B] p-6 shadow-[0_4px_32px_rgba(0,0,0,0.07)] dark:shadow-none"
        >
          <div className="mb-4">
            <label className="block mb-1.5 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
              E-mail
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#AEAEBF] dark:text-[#6E6E7C]" strokeWidth={1.8} />
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="voce@escritorio.com.br"
                className="w-full pl-9 pr-3 py-2.5 rounded-xl border border-[#E4E4EC] dark:border-[#2A2A32] bg-[#FAFAFA] dark:bg-[#1C1C21] text-[#0F1117] dark:text-[#ECECEF] placeholder:text-[#C0C0CE] dark:placeholder:text-[#4A4A54] outline-none focus:border-[#1A3A5C] dark:focus:border-[#8AB0DC] focus:ring-2 focus:ring-[#1A3A5C]/10 dark:focus:ring-[#8AB0DC]/10 transition-all"
                style={{ fontSize: "14.9px" }}
              />
            </div>
          </div>

          <div className="mb-2">
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
                Senha
              </label>
              <button
                type="button"
                onClick={() => router.push("/esqueci-senha")}
                className="text-[#1A3A5C] dark:text-[#8AB0DC] hover:underline"
                style={{ fontSize: "12.6px" }}
              >
                Esqueceu a senha?
              </button>
            </div>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#AEAEBF] dark:text-[#6E6E7C]" strokeWidth={1.8} />
              <input
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-9 pr-9 py-2.5 rounded-xl border border-[#E4E4EC] dark:border-[#2A2A32] bg-[#FAFAFA] dark:bg-[#1C1C21] text-[#0F1117] dark:text-[#ECECEF] placeholder:text-[#C0C0CE] dark:placeholder:text-[#4A4A54] outline-none focus:border-[#1A3A5C] dark:focus:border-[#8AB0DC] focus:ring-2 focus:ring-[#1A3A5C]/10 dark:focus:ring-[#8AB0DC]/10 transition-all"
                style={{ fontSize: "14.9px" }}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#AEAEBF] dark:text-[#6E6E7C] hover:text-[#4A4A5A] dark:hover:text-[#C4C4CE] transition-colors"
                title={showPassword ? "Ocultar senha" : "Mostrar senha"}
              >
                {showPassword ? <EyeOff className="w-4 h-4" strokeWidth={1.8} /> : <Eye className="w-4 h-4" strokeWidth={1.8} />}
              </button>
            </div>
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
            {loading ? (
              "Entrando…"
            ) : (
              <>
                Entrar
                <ArrowRight className="w-4 h-4" strokeWidth={2} />
              </>
            )}
          </button>
        </form>

        <p className="text-center text-[#AEAEBF] dark:text-[#6E6E7C] mt-5" style={{ fontSize: "12.6px" }}>
          Acesso restrito a advogados e assistentes jurídicos.
          <br />
          Não tem conta?{" "}
          <button
            type="button"
            onClick={() => router.push("/registro")}
            className="text-[#1A3A5C] dark:text-[#8AB0DC] hover:underline"
          >
            Criar conta
          </button>
        </p>
      </div>
    </div>
  );
}
