import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Eye, EyeOff } from "lucide-react";

const BORDA_NORMAL =
  "border-[#E4E4EC] dark:border-[#2A2A32] focus:border-[#1A3A5C] dark:focus:border-[#8AB0DC] focus:ring-[#1A3A5C]/10 dark:focus:ring-[#8AB0DC]/10";
const BORDA_ERRO =
  "border-[#C44040] dark:border-[#D96B6B] focus:border-[#C44040] dark:focus:border-[#D96B6B] focus:ring-[#C44040]/10 dark:focus:ring-[#D96B6B]/10";

/** Campo das telas públicas: rótulo, ícone, input e, opcionalmente, o olho de mostrar senha
 *  (`olho`), uma mensagem de erro (`erro`, que também pinta a borda) e um `acao` ao lado do
 *  rótulo (ex.: "Esqueceu a senha?"). `ultimo` troca a margem de baixo (mb-4 → mb-2). */
export function CampoAuth({
  rotulo,
  icone: Icone,
  valor,
  onChange,
  placeholder,
  type = "text",
  autoComplete,
  autoFocus,
  olho,
  erro,
  acao,
  ultimo,
}: {
  rotulo: string;
  icone: LucideIcon;
  valor: string;
  onChange: (valor: string) => void;
  placeholder: string;
  type?: "text" | "email" | "password";
  autoComplete: string;
  autoFocus?: boolean;
  /** Mostra o olho; `visivel` vira type="text" e `alternar` troca o estado. */
  olho?: { visivel: boolean; alternar: () => void };
  erro?: string;
  acao?: ReactNode;
  ultimo?: boolean;
}) {
  const rotuloOlho = olho?.visivel ? "Ocultar senha" : "Mostrar senha";
  return (
    <div className={ultimo ? "mb-2" : "mb-4"}>
      <div className="flex items-center justify-between mb-1.5">
        <label className="text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
          {rotulo}
        </label>
        {acao}
      </div>
      <div className="relative">
        <Icone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#AEAEBF] dark:text-[#6E6E7C]" strokeWidth={1.8} />
        <input
          type={olho?.visivel ? "text" : type}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          value={valor}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={`w-full pl-9 ${olho ? "pr-9" : "pr-3"} py-2.5 rounded-xl border bg-[#FAFAFA] dark:bg-[#1C1C21] text-[#0F1117] dark:text-[#ECECEF] placeholder:text-[#AEAEBF] dark:placeholder:text-[#6E6E7C] outline-none focus:ring-2 transition-all ${
            erro ? BORDA_ERRO : BORDA_NORMAL
          }`}
          style={{ fontSize: "14.9px" }}
        />
        {olho && (
          <button
            type="button"
            onClick={olho.alternar}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-[#AEAEBF] dark:text-[#6E6E7C] hover:text-[#4A4A5A] dark:hover:text-[#C4C4CE] transition-colors"
            title={rotuloOlho}
            aria-label={rotuloOlho}
            aria-pressed={olho.visivel}
          >
            {olho.visivel ? <EyeOff className="w-4 h-4" strokeWidth={1.8} /> : <Eye className="w-4 h-4" strokeWidth={1.8} />}
          </button>
        )}
      </div>
      {erro && (
        <p className="mt-1.5 text-[#C44040] dark:text-[#D96B6B]" style={{ fontSize: "12.1px" }}>
          {erro}
        </p>
      )}
    </div>
  );
}
