import { AppShell } from "@/components/app-shell";
import { ConversationsProvider } from "@/lib/conversations";

/** Layout das telas autenticadas: provê as conversas e a casca com a sidebar. */
export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <ConversationsProvider>
      <AppShell>{children}</AppShell>
    </ConversationsProvider>
  );
}
