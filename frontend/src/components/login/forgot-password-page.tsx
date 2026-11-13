"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Mail, ArrowRight, MailCheck } from "lucide-react";
import { pedirRedefinicaoSenha } from "@/lib/api";
import { AuthShell, BotaoAuth, LinkVoltar, PainelSucesso } from "./auth-shell";
import { CampoAuth } from "./campo-auth";

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
    <AuthShell
      titulo="Recuperar senha"
      subtitulo="Informe seu e-mail para receber um link de redefinição"
      rodape={<LinkVoltar onClick={() => router.push("/login")}>Voltar para o login</LinkVoltar>}
    >
      {sent ? (
        <PainelSucesso
          icone={MailCheck}
          titulo="Verifique seu e-mail"
          texto={
            <>
              Se <strong className="text-[#4A4A5A] dark:text-[#C4C4CE]">{email}</strong> estiver cadastrado, você vai
              receber um link para redefinir sua senha em instantes. Ele vale por 30 minutos; confira
              também a caixa de spam.
            </>
          }
        />
      ) : (
        <form onSubmit={handleSubmit}>
          <CampoAuth
            rotulo="E-mail"
            icone={Mail}
            type="email"
            autoComplete="email"
            autoFocus
            valor={email}
            onChange={setEmail}
            placeholder="voce@escritorio.com.br"
            ultimo
          />

          {error && (
            <p role="alert" className="mt-3 text-[#A1362F] dark:text-[#F0938B]" style={{ fontSize: "13.2px" }}>
              {error}
            </p>
          )}

          <BotaoAuth disabled={!canSubmit}>
            {loading ? (
              "Enviando…"
            ) : (
              <>
                Enviar link de redefinição
                <ArrowRight className="w-4 h-4" strokeWidth={2} />
              </>
            )}
          </BotaoAuth>
        </form>
      )}
    </AuthShell>
  );
}
