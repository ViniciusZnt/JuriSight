import { AppShell } from "@/components/app-shell";
import { ConversationsProvider } from "@/lib/conversations";
import { SavedProvider } from "@/lib/saved";
import { RequireAuth } from "@/lib/auth";

/** Layout das telas autenticadas: exige sessão, provê as conversas, os salvos e a casca com a sidebar. */
export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <ConversationsProvider>
        <SavedProvider>
          <AppShell>{children}</AppShell>
        </SavedProvider>
      </ConversationsProvider>
    </RequireAuth>
  );
}
