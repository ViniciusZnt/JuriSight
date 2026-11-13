"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Lock, Mail, ArrowRight } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { AuthShell, BotaoAuth, CaixaErro } from "./auth-shell";
import { CampoAuth } from "./campo-auth";

/** Login real — POST /auth/login (query/api/auth_routes.py), sessão via cookie httpOnly. */
export function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = email.trim().length > 0 && password.length > 0 && !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    setLoading(true);
    try {
      await login(email.trim(), password);
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível entrar. Tente novamente.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      titulo="JuriSight"
      subtitulo="Pesquisa contextual de jurisprudência trabalhista"
      rodape={
        <p className="text-center text-[#6B6B80] dark:text-[#9494A2] mt-5" style={{ fontSize: "12.6px" }}>
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
      }
    >
      <form onSubmit={handleSubmit}>
        {error && <CaixaErro>{error}</CaixaErro>}

        <CampoAuth
          rotulo="E-mail"
          icone={Mail}
          type="email"
          autoComplete="email"
          valor={email}
          onChange={setEmail}
          placeholder="voce@escritorio.com.br"
        />
        <CampoAuth
          rotulo="Senha"
          icone={Lock}
          autoComplete="current-password"
          type="password"
          valor={password}
          onChange={setPassword}
          placeholder="••••••••"
          olho={{ visivel: showPassword, alternar: () => setShowPassword((v) => !v) }}
          ultimo
          acao={
            <button
              type="button"
              onClick={() => router.push("/esqueci-senha")}
              className="text-[#1A3A5C] dark:text-[#8AB0DC] hover:underline"
              style={{ fontSize: "12.6px" }}
            >
              Esqueceu a senha?
            </button>
          }
        />

        <BotaoAuth disabled={!canSubmit}>
          {loading ? (
            "Entrando…"
          ) : (
            <>
              Entrar
              <ArrowRight className="w-4 h-4" strokeWidth={2} />
            </>
          )}
        </BotaoAuth>
      </form>
    </AuthShell>
  );
}
