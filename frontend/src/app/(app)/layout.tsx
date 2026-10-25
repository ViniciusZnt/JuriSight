import { AppShell } from "@/components/app-shell";
import { ConversationsProvider } from "@/lib/conversations";
import { SavedProvider } from "@/lib/saved";
import { ProfileProvider } from "@/lib/profile";
import { RequireAuth } from "@/lib/auth";
import { SearchSessionProvider } from "@/lib/search-session";

/** Layout das telas autenticadas: exige sessão, provê as conversas, os salvos, o perfil, o
 *  estado do fluxo de busca (Home -> Revisão -> Resultados -> Decisão) e a casca com a sidebar. */
export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <ProfileProvider>
        <ConversationsProvider>
          <SavedProvider>
            <SearchSessionProvider>
              <AppShell>{children}</AppShell>
            </SearchSessionProvider>
          </SavedProvider>
        </ConversationsProvider>
      </ProfileProvider>
    </RequireAuth>
  );
}
