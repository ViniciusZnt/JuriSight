"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Lock, ArrowRight, CheckCircle2 } from "lucide-react";
import { redefinirSenha } from "@/lib/api";
import { AuthShell, BotaoAuth, PainelSucesso } from "./auth-shell";
import { CampoAuth } from "./campo-auth";

/** Mesmo mínimo do cadastro (RegistroRequest no backend). */
const SENHA_MINIMA = 8;

/** Redefinir senha — o link do e-mail traz `?token=`, validado pelo backend (POST
 *  /auth/redefinir-senha): uso único e 30 minutos de validade (issue #14). */
export function ResetPasswordPage() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [error, setError] = useState<string | null>(
    token ? null : "Este endereço não tem o link de redefinição. Abra o link que chegou por e-mail ou peça um novo."
  );
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const passwordTooShort = password.length > 0 && password.length < SENHA_MINIMA;
  const passwordsMismatch = confirmPassword.length > 0 && password !== confirmPassword;
  const canSubmit = !!token && password.length >= SENHA_MINIMA && confirmPassword === password && !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    try {
      await redefinirSenha(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível redefinir a senha. Tente de novo.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell titulo="Redefinir senha" subtitulo="Escolha uma nova senha para sua conta">
      {done ? (
        <PainelSucesso icone={CheckCircle2} titulo="Senha redefinida" texto="Sua senha foi alterada com sucesso. Entre com a nova senha.">
          <BotaoAuth type="button" onClick={() => router.push("/login")}>
            Ir para o login
            <ArrowRight className="w-4 h-4" strokeWidth={2} />
          </BotaoAuth>
        </PainelSucesso>
      ) : (
        <form onSubmit={handleSubmit}>
          <CampoAuth
            rotulo="Nova senha"
            icone={Lock}
            type="password"
            autoComplete="new-password"
            autoFocus
            valor={password}
            onChange={setPassword}
            placeholder={`Mínimo ${SENHA_MINIMA} caracteres`}
            olho={{ visivel: showPassword, alternar: () => setShowPassword((v) => !v) }}
            erro={passwordTooShort ? `A senha precisa ter pelo menos ${SENHA_MINIMA} caracteres.` : undefined}
          />
          <CampoAuth
            rotulo="Confirmar nova senha"
            icone={Lock}
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            valor={confirmPassword}
            onChange={setConfirmPassword}
            placeholder="Repita a nova senha"
            erro={passwordsMismatch ? "As senhas não coincidem." : undefined}
            ultimo
          />

          {error && (
            <p role="alert" className="mt-3 text-[#A1362F] dark:text-[#F0938B]" style={{ fontSize: "13.2px" }}>
              {error}{" "}
              <a href="/esqueci-senha" className="underline underline-offset-2">
                Pedir um novo link
              </a>
            </p>
          )}

          <BotaoAuth disabled={!canSubmit}>{loading ? "Salvando…" : "Redefinir senha"}</BotaoAuth>
        </form>
      )}
    </AuthShell>
  );
}
