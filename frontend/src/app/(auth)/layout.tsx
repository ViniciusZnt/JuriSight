import { RequireGuest } from "@/lib/auth";

/** Layout das telas públicas (login, cadastro, recuperação de senha): quem já tem sessão é
 *  redirecionado para o app. */
export default function AuthGroupLayout({ children }: { children: React.ReactNode }) {
  return <RequireGuest>{children}</RequireGuest>;
}
