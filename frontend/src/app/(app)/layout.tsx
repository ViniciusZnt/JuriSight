import { AppShell } from "@/components/app-shell";
import { ConversationsProvider } from "@/lib/conversations";
import { SavedProvider } from "@/lib/saved";
import { ProfileProvider } from "@/lib/profile";
import { RequireAuth } from "@/lib/auth";

/** Layout das telas autenticadas: exige sessão, provê as conversas, os salvos, o perfil e a casca com a sidebar. */
export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <ProfileProvider>
        <ConversationsProvider>
          <SavedProvider>
            <AppShell>{children}</AppShell>
          </SavedProvider>
        </ConversationsProvider>
      </ProfileProvider>
    </RequireAuth>
  );
}
