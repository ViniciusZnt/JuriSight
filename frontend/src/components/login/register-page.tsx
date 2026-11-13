"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Lock, Mail, User, ArrowRight } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { ApiError, registrarUsuario } from "@/lib/api";
import { AuthShell, BotaoAuth, CaixaErro, LinkVoltar } from "./auth-shell";
import { CampoAuth } from "./campo-auth";

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
    <AuthShell
      titulo="Criar conta"
      subtitulo="Cadastro de advogados e assistentes jurídicos"
      rodape={<LinkVoltar onClick={() => router.push("/login")}>Já tem conta? Entrar</LinkVoltar>}
    >
      <form onSubmit={handleSubmit}>
        {error && <CaixaErro>{error}</CaixaErro>}

        <CampoAuth rotulo="Nome completo" icone={User} autoComplete="name" valor={name} onChange={setName} placeholder="Seu nome" />
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
          type="password"
          autoComplete="new-password"
          valor={password}
          onChange={setPassword}
          placeholder={`Mínimo ${SENHA_MIN_LENGTH} caracteres`}
          olho={{ visivel: showPassword, alternar: () => setShowPassword((v) => !v) }}
          erro={passwordTooShort ? `A senha precisa ter pelo menos ${SENHA_MIN_LENGTH} caracteres.` : undefined}
        />
        <CampoAuth
          rotulo="Confirmar senha"
          icone={Lock}
          type={showPassword ? "text" : "password"}
          autoComplete="new-password"
          valor={confirmPassword}
          onChange={setConfirmPassword}
          placeholder="Repita a senha"
          erro={passwordsMismatch ? "As senhas não coincidem." : undefined}
          ultimo
        />

        <BotaoAuth disabled={!canSubmit}>
          {loading ? (
            "Criando conta…"
          ) : (
            <>
              Criar conta
              <ArrowRight className="w-4 h-4" strokeWidth={2} />
            </>
          )}
        </BotaoAuth>
      </form>
    </AuthShell>
  );
}
