import { ThemeToggle } from "@/components/settings/theme-toggle";

/** Configurações — aparência (tema) funcional; demais seções a preencher. */
export default function ConfiguracoesPage() {
  return (
    <div className="min-h-full bg-[#F7F7F9]">
      <header className="pl-20 pr-8 py-4">
        <h1 className="text-[#0F1117]" style={{ fontSize: "18px", fontWeight: 600 }}>
          Configurações
        </h1>
      </header>

      <div className="mx-auto max-w-2xl px-4 sm:px-8 pb-12">
        <section className="mt-2">
          <p className="mb-2 px-1 text-[#8A8A9A] uppercase tracking-wide" style={{ fontSize: "11px", fontWeight: 600 }}>
            Aparência
          </p>
          <ThemeToggle />
        </section>

        <section className="mt-8">
          <p className="mb-2 px-1 text-[#8A8A9A] uppercase tracking-wide" style={{ fontSize: "11px", fontWeight: 600 }}>
            Conta
          </p>
          <div className="rounded-xl border border-[#EAEAEF] bg-white px-4 py-3.5">
            <p className="text-[#0F1117]" style={{ fontSize: "13.5px", fontWeight: 600 }}>
              Marcos Almeida
            </p>
            <p className="text-[#8A8A9A]" style={{ fontSize: "12px" }}>
              Plano Pro • em breve
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
