"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Mail, ArrowRight, ArrowLeft, MailCheck } from "lucide-react";
import { pedirRedefinicaoSenha } from "@/lib/api";

/** Esqueci minha senha — o backend manda um link de uso único por e-mail (POST
 *  /auth/esqueci-senha). Não revela se o e-mail existe na base. Se o servidor não tiver envio
 *  de e-mail configurado, mostra o aviso dele em vez de fingir que enviou (issue #14). */
export function ForgotPasswordPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = email.trim().length > 0 && !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    try {
      await pedirRedefinicaoSenha(email.trim());
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível pedir o link agora. Tente de novo.");
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
            Recuperar senha
          </h1>
          <p className="text-[#6B6B80] dark:text-[#9494A2] mt-1 text-center" style={{ fontSize: "13.8px" }}>
            Informe seu e-mail para receber um link de redefinição
          </p>
        </div>

        <div className="rounded-2xl border border-[#E4E4EC] dark:border-[#26262C] bg-white dark:bg-[#17171B] p-6 shadow-[0_4px_32px_rgba(0,0,0,0.07)] dark:shadow-none">
          {sent ? (
            <div className="flex flex-col items-center text-center py-2">
              <div className="w-12 h-12 rounded-xl bg-[#EDF7F2] dark:bg-[#122A1E] flex items-center justify-center mb-4">
                <MailCheck className="w-5 h-5 text-[#1E6B4A] dark:text-[#6FCB9A]" strokeWidth={1.8} />
              </div>
              <p className="text-[#0F1117] dark:text-[#ECECEF] mb-1.5" style={{ fontSize: "15.5px", fontWeight: 600 }}>
                Verifique seu e-mail
              </p>
              <p className="text-[#6B6B80] dark:text-[#9494A2] leading-relaxed" style={{ fontSize: "13.8px" }}>
                Se <strong className="text-[#4A4A5A] dark:text-[#C4C4CE]">{email}</strong> estiver cadastrado, você vai
                receber um link para redefinir sua senha em instantes. Ele vale por 30 minutos; confira
                também a caixa de spam.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <div className="mb-2">
                <label className="block mb-1.5 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
                  E-mail
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#AEAEBF] dark:text-[#6E6E7C]" strokeWidth={1.8} />
                  <input
                    type="email"
                    autoComplete="email"
                    autoFocus
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="voce@escritorio.com.br"
                    className="w-full pl-9 pr-3 py-2.5 rounded-xl border border-[#E4E4EC] dark:border-[#2A2A32] bg-[#FAFAFA] dark:bg-[#1C1C21] text-[#0F1117] dark:text-[#ECECEF] placeholder:text-[#AEAEBF] dark:placeholder:text-[#6E6E7C] outline-none focus:border-[#1A3A5C] dark:focus:border-[#8AB0DC] focus:ring-2 focus:ring-[#1A3A5C]/10 dark:focus:ring-[#8AB0DC]/10 transition-all"
                    style={{ fontSize: "14.9px" }}
                  />
                </div>
              </div>

              {error && (
                <p role="alert" className="mt-3 text-[#A1362F] dark:text-[#F0938B]" style={{ fontSize: "13.2px" }}>
                  {error}
                </p>
              )}

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
                  "Enviando…"
                ) : (
                  <>
                    Enviar link de redefinição
                    <ArrowRight className="w-4 h-4" strokeWidth={2} />
                  </>
                )}
              </button>
            </form>
          )}
        </div>

        <button
          type="button"
          onClick={() => router.push("/login")}
          className="flex items-center justify-center gap-1.5 w-full mt-5 text-[#6B6B80] dark:text-[#A6A6B4] hover:text-[#1A3A5C] dark:hover:text-[#8AB0DC] transition-colors"
          style={{ fontSize: "13.2px" }}
        >
          <ArrowLeft className="w-3.5 h-3.5" strokeWidth={1.8} />
          Voltar para o login
        </button>
      </div>
    </div>
  );
}
