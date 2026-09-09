import { AppShell } from "@/components/app-shell";
import { ConversationsProvider } from "@/lib/conversations";
import { SavedProvider } from "@/lib/saved";
import { ProfileProvider } from "@/lib/profile";
import { ConsultaProvider } from "@/lib/consulta";
import { RequireAuth } from "@/lib/auth";

/** Layout das telas autenticadas: exige sessão, provê as conversas, os salvos, o perfil, a consulta em andamento e a casca com a sidebar. */
export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <ProfileProvider>
        <ConversationsProvider>
          <SavedProvider>
            <ConsultaProvider>
              <AppShell>{children}</AppShell>
            </ConsultaProvider>
          </SavedProvider>
        </ConversationsProvider>
      </ProfileProvider>
    </RequireAuth>
  );
}
