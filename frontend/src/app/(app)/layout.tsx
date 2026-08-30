import { AppShell } from "@/components/app-shell";
import { ConversationsProvider } from "@/lib/conversations";
import { SavedProvider } from "@/lib/saved";

/** Layout das telas autenticadas: provê as conversas, os salvos e a casca com a sidebar. */
export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <ConversationsProvider>
      <SavedProvider>
        <AppShell>{children}</AppShell>
      </SavedProvider>
    </ConversationsProvider>
  );
}
