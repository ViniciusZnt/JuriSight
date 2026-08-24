import { FileText, Sparkles, Scale, Check, type LucideIcon } from "lucide-react";

interface Step {
  label: string;
  icon: LucideIcon;
}

const STEPS: Step[] = [
  { label: "Documento enviado", icon: FileText },
  { label: "Revisão de contexto", icon: Sparkles },
  { label: "Jurisprudências", icon: Scale },
];

/** Trilha de progresso do fluxo de consulta (Home → Revisão → Resultados). `current` é 0-indexado. */
export function StepIndicator({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-2 sm:gap-4 mb-8 overflow-x-auto max-w-full whitespace-nowrap pb-1">
      {STEPS.map((step, idx) => {
        const Icon = step.icon;
        const done = idx < current;
        const active = idx === current;

        return (
          <div key={step.label} className="flex items-center gap-2 sm:gap-4">
            {idx > 0 && (
              <div
                className={`h-0.5 w-6 sm:w-10 rounded-full transition-colors ${
                  idx <= current ? "bg-[#2D8A5F] dark:bg-[#3DA372]" : "bg-[#D8D8E4] dark:bg-[#2A2A32]"
                }`}
              />
            )}
            <div className="flex items-center gap-2">
              <div
                className={`flex items-center justify-center w-8 h-8 rounded-full flex-shrink-0 border transition-colors ${
                  done
                    ? "bg-[#2D8A5F] dark:bg-[#3DA372] border-[#2D8A5F] dark:border-[#3DA372]"
                    : active
                      ? "bg-[#1A3A5C] dark:bg-[#8AB0DC] border-[#1A3A5C] dark:border-[#8AB0DC] shadow-[0_0_0_4px_rgba(26,58,92,0.12)] dark:shadow-[0_0_0_4px_rgba(138,176,220,0.16)]"
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
              </div>
              <span
                className={
                  done
                    ? "text-[#1A5C3A] dark:text-[#6FCB9A]"
                    : active
                      ? "text-[#1A3A5C] dark:text-[#8AB0DC]"
                      : "text-[#9090A8] dark:text-[#7C7C88]"
                }
                style={{ fontSize: "14.4px", fontWeight: active ? 600 : 500 }}
              >
                {step.label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
