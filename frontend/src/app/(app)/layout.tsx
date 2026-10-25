import { AppShell } from "@/components/app-shell";

/** Layout das telas autenticadas: envolve tudo na casca com a sidebar. */
export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
