"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Lock, Mail, User, ArrowRight, ArrowLeft, AlertCircle } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { ApiError, registrarUsuario } from "@/lib/api";

// Mínimo real exigido por POST /auth/registro (query/api/auth_routes.py::RegistroRequest) —
// tem que bater com o backend pra não confundir o usuário com um 422 depois de passar
// pela validação do próprio formulário.
const SENHA_MIN_LENGTH = 8;

/** Cadastro real — POST /auth/registro, seguido de login automático (o registro não seta
 *  cookie sozinho) pra entrar direto na aplicação, como o fluxo anterior já fazia. */
export function RegisterPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const passwordTooShort = password.length > 0 && password.length < SENHA_MIN_LENGTH;
  const passwordsMismatch = confirmPassword.length > 0 && password !== confirmPassword;
  const formValid =
    name.trim().length > 0 &&
    email.trim().length > 0 &&
    password.length >= SENHA_MIN_LENGTH &&
    confirmPassword === password;
  const canSubmit = formValid && !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    setLoading(true);
    try {
      await registrarUsuario({ email: email.trim(), password, nome: name.trim() });
      await login(email.trim(), password);
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível criar a conta. Tente novamente.");
    } finally {
      setLoading(false);
    }
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
            Criar conta
          </h1>
          <p className="text-[#8A8A9A] dark:text-[#9494A2] mt-1 text-center" style={{ fontSize: "13.8px" }}>
            Cadastro de advogados e assistentes jurídicos
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-[#E4E4EC] dark:border-[#26262C] bg-white dark:bg-[#17171B] p-6 shadow-[0_4px_32px_rgba(0,0,0,0.07)] dark:shadow-none"
        >
          {error && (
            <div className="mb-4 flex items-start gap-2 rounded-xl border border-[#E8C2C2] dark:border-[#4A2529] bg-[#FBF0F0] dark:bg-[#2A1517] px-3 py-2.5">
              <AlertCircle className="w-4 h-4 text-[#C44040] dark:text-[#D96B6B] mt-0.5 flex-shrink-0" strokeWidth={1.8} />
              <p className="text-[#7A1A1A] dark:text-[#E08A93]" style={{ fontSize: "13.2px" }}>{error}</p>
            </div>
          )}

          <div className="mb-4">
            <label className="block mb-1.5 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
              Nome completo
            </label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#AEAEBF] dark:text-[#6E6E7C]" strokeWidth={1.8} />
              <input
                type="text"
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Seu nome"
                className="w-full pl-9 pr-3 py-2.5 rounded-xl border border-[#E4E4EC] dark:border-[#2A2A32] bg-[#FAFAFA] dark:bg-[#1C1C21] text-[#0F1117] dark:text-[#ECECEF] placeholder:text-[#C0C0CE] dark:placeholder:text-[#4A4A54] outline-none focus:border-[#1A3A5C] dark:focus:border-[#8AB0DC] focus:ring-2 focus:ring-[#1A3A5C]/10 dark:focus:ring-[#8AB0DC]/10 transition-all"
                style={{ fontSize: "14.9px" }}
              />
            </div>
          </div>

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

          <div className="mb-4">
            <label className="block mb-1.5 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
              Senha
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#AEAEBF] dark:text-[#6E6E7C]" strokeWidth={1.8} />
              <input
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={`Mínimo ${SENHA_MIN_LENGTH} caracteres`}
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
                A senha precisa ter pelo menos {SENHA_MIN_LENGTH} caracteres.
              </p>
            )}
          </div>

          <div className="mb-2">
            <label className="block mb-1.5 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
              Confirmar senha
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#AEAEBF] dark:text-[#6E6E7C]" strokeWidth={1.8} />
              <input
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Repita a senha"
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
            {loading ? (
              "Criando conta…"
            ) : (
              <>
                Criar conta
                <ArrowRight className="w-4 h-4" strokeWidth={2} />
              </>
            )}
          </button>
        </form>

        <button
          type="button"
          onClick={() => router.push("/login")}
          className="flex items-center justify-center gap-1.5 w-full mt-5 text-[#6B6B80] dark:text-[#A6A6B4] hover:text-[#1A3A5C] dark:hover:text-[#8AB0DC] transition-colors"
          style={{ fontSize: "13.2px" }}
        >
          <ArrowLeft className="w-3.5 h-3.5" strokeWidth={1.8} />
          Já tem conta? Entrar
        </button>
      </div>
    </div>
  );
}
