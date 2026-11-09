import { Suspense } from "react";
import { ResetPasswordPage } from "@/components/login/reset-password-page";

/** Redefinir senha — fora da casca autenticada (sem sidebar). O Suspense é exigido pelo
 *  useSearchParams (o token vem na URL do link enviado por e-mail). */
export default function RedefinirSenha() {
  return (
    <Suspense>
      <ResetPasswordPage />
    </Suspense>
  );
}
