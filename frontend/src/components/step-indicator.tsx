import { FileText, MessageSquare, Sparkles, Scale, Check, Pencil, type LucideIcon } from "lucide-react";

interface Step {
  label: string;
  icon: LucideIcon;
}

const STEPS: Step[] = [
  { label: "Documento enviado", icon: FileText },
  { label: "Revisão de contexto", icon: Sparkles },
  { label: "Jurisprudências", icon: Scale },
];
const REVISAO = 1;

/** UC02 — sem PDF: o primeiro passo não envolveu upload, então o rótulo reflete a intenção
 *  argumentativa digitada em vez de um documento enviado. */
const MANUAL_FIRST_STEP: Step = { label: "Consulta iniciada", icon: MessageSquare };

/** Trilha de progresso do fluxo de consulta (Home → Revisão → Resultados). `current` é 0-indexado.
 *  `manual` reflete o UC02 (busca sem PDF, ver FA01 na RFC). Com `onEditarRevisao`, o passo da
 *  revisão ganha um lápis que volta para ela. */
export function StepIndicator({ current, manual = false, onEditarRevisao }: { current: number; manual?: boolean; onEditarRevisao?: () => void }) {
  const steps = manual ? [MANUAL_FIRST_STEP, ...STEPS.slice(1)] : STEPS;
  return (
    // p-2: o anel do passo atual não é cortado pela rolagem horizontal do celular
    <div className="w-full flex justify-center mb-7">
      <div className="max-w-full overflow-x-auto">
        <ol className="flex items-center gap-2 sm:gap-3 w-max mx-auto p-2 px-3 sm:px-4 rounded-full bg-white/70 dark:bg-[#17171B]/70 border border-[#E8E8F0] dark:border-[#26262C]">
          {steps.map((step, idx) => {
            const Icon = step.icon;
            const done = idx < current;
            const active = idx === current;
            return (
              <li key={step.label} className="flex items-center gap-2 sm:gap-3">
                {idx > 0 && (
                  <span
                    aria-hidden
                    className={`h-0.5 w-6 sm:w-10 rounded-full transition-colors ${
                      idx <= current ? "bg-[#2D8A5F] dark:bg-[#3DA372]" : "bg-[#D8D8E4] dark:bg-[#2A2A32]"
                    }`}
                  />
                )}
                <span className="flex items-center gap-2" aria-current={active ? "step" : undefined}>
                  <span
                    className={`flex items-center justify-center w-8 h-8 rounded-full flex-shrink-0 border transition-colors ${
                      done
                        ? "bg-[#2D8A5F] dark:bg-[#3DA372] border-[#2D8A5F] dark:border-[#3DA372]"
                        : active
                          ? "bg-[#1A3A5C] dark:bg-[#8AB0DC] border-[#1A3A5C] dark:border-[#8AB0DC] ring-4 ring-[#1A3A5C]/12 dark:ring-[#8AB0DC]/20"
                          : "bg-white dark:bg-[#17171B] border-[#D0D0DA] dark:border-[#3A3A42]"
                    }`}
                  >
                    {done ? (
                      <Check className="w-4 h-4 text-white" strokeWidth={2.5} />
                    ) : (
                      <Icon
                        className={active ? "w-4 h-4 text-white dark:text-[#0E0E11]" : "w-4 h-4 text-[#AEAEBF] dark:text-[#6E6E7C]"}
                        strokeWidth={1.8}
                      />
                    )}
                  </span>
                  {/* No celular só o passo atual mostra o rótulo; os outros ficam só com o ícone. */}
                  <span
                    className={
                      done
                        ? "hidden sm:inline text-[#1A5C3A] dark:text-[#6FCB9A]"
                        : active
                          ? "text-[#1A3A5C] dark:text-[#8AB0DC]"
                          : "hidden sm:inline text-[#9090A8] dark:text-[#7C7C88]"
                    }
                    style={{ fontSize: "14.4px", fontWeight: active ? 600 : 500 }}
                  >
                    {step.label}
                  </span>
                  {idx === REVISAO && onEditarRevisao && (
                    <button
                      type="button"
                      onClick={onEditarRevisao}
                      aria-label="Editar a revisão de contexto"
                      title="Editar a revisão de contexto"
                      className="flex items-center justify-center w-7 h-7 rounded-full border border-[#C8D9EF] dark:border-[#2A3A4C] bg-[#EEF3FB] dark:bg-[#1A2A3C] text-[#1A3A5C] dark:text-[#8AB0DC] hover:bg-[#1A3A5C] hover:text-white hover:border-[#1A3A5C] dark:hover:bg-[#8AB0DC] dark:hover:text-[#0E0E11] transition-colors"
                    >
                      <Pencil className="w-3.5 h-3.5" strokeWidth={2} />
                    </button>
                  )}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
