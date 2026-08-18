"use client";

import { useRouter } from "next/navigation";
import { BookOpen, FileSearch, Gavel, Star, Zap } from "lucide-react";
import { SearchInput } from "@/components/home/search-input";

const features = [
  {
    icon: FileSearch,
    title: "Busca contextual",
    description: "Pesquisa por semelhança semântica de teses argumentativas, não apenas por palavras-chave.",
    color: "#1A3A5C",
    bg: "#EFF4FA",
  },
  {
    icon: Gavel,
    title: "Jurisprudência atualizada",
    description: "Acesso às últimas decisões do TST, TRT e STF com indexação em tempo real.",
    color: "#1E6B4A",
    bg: "#EDF7F2",
  },
  {
    icon: BookOpen,
    title: "Análise argumentativa",
    description: "IA identifica decisões favoráveis e desfavoráveis alinhadas à sua linha de defesa.",
    color: "#7A4A1A",
    bg: "#FBF4EC",
  },
];

/** Home: entrada de consulta (RFC Figura 2). Ao enviar, vai para a revisão. */
export function HomePage() {
  const router = useRouter();
  const handleSubmit = () => router.push("/revisao");

  return (
    <div className="flex flex-col min-h-full bg-[#F7F7F9]">
      {/* Topbar — pl-20 abre espaço para o botão de recolher a sidebar */}
      <header className="flex items-center justify-between gap-3 pl-20 pr-4 sm:pr-8 py-4 bg-[#F7F7F9] sticky top-0 z-10">
        <span className="text-[#C0C0CE] truncate" style={{ fontSize: "12.5px" }}>
          Início
        </span>

        <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white border border-[#E0E0EA] shadow-[0_1px_4px_rgba(0,0,0,0.04)]">
            <Star className="w-3 h-3 text-[#C19A2E]" strokeWidth={2} fill="currentColor" />
            <span className="text-[#4A4A5A]" style={{ fontSize: "11.5px", fontWeight: 500 }}>Plano Pro</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white border border-[#E0E0EA] shadow-[0_1px_4px_rgba(0,0,0,0.04)]">
            <Zap className="w-3 h-3 text-[#1A3A5C]" strokeWidth={2} />
            <span className="text-[#4A4A5A]" style={{ fontSize: "11.5px", fontWeight: 500 }}>47 consultas restantes</span>
          </div>
        </div>
      </header>

      {/* Hero */}
      <div className="flex flex-col items-center justify-center px-4 sm:px-8 pt-8 sm:pt-12 pb-8">
        <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#EFF4FA] border border-[#D0DEEE] mb-6 sm:mb-8">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.png" alt="JuriSight" className="w-4 h-4 object-contain select-none" draggable={false} />
          <span className="text-[#1A3A5C] tracking-[0.02em]" style={{ fontSize: "11.5px", fontWeight: 600 }}>
            IA Jurídica Trabalhista
          </span>
        </div>

        <h1
          className="text-center text-[#0F1117] tracking-[-0.03em] max-w-[600px] leading-tight px-2"
          style={{ fontSize: "clamp(24px, 5vw, 36px)", fontWeight: 600 }}
        >
          Pesquisa contextual de
          <br />
          <span className="text-[#1A3A5C]">jurisprudência trabalhista</span>
        </h1>

        <p
          className="text-center text-[#7A7A8E] mt-4 max-w-[480px] leading-relaxed px-2"
          style={{ fontSize: "15.5px", fontWeight: 400 }}
        >
          Encontre decisões alinhadas à sua tese argumentativa com inteligência semântica.
          TST, TRT e STF indexados em tempo real.
        </p>

        <div className="w-full max-w-[720px] mt-8 sm:mt-10">
          <SearchInput onSubmit={handleSubmit} />
        </div>
      </div>

      {/* Features */}
      <div className="px-4 sm:px-8 pb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-[880px] mx-auto">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <div
                key={feature.title}
                className="bg-white rounded-xl p-5 border border-[#EAEAEF] shadow-[0_1px_6px_rgba(0,0,0,0.04)] hover:shadow-[0_2px_12px_rgba(0,0,0,0.07)] transition-all cursor-default"
              >
                <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-3" style={{ background: feature.bg }}>
                  <Icon style={{ color: feature.color, width: "18px", height: "18px" }} strokeWidth={1.8} />
                </div>
                <h3 className="text-[#0F1117] mb-1.5" style={{ fontSize: "13.5px", fontWeight: 600 }}>
                  {feature.title}
                </h3>
                <p className="text-[#8A8A9A] leading-relaxed" style={{ fontSize: "12.5px" }}>
                  {feature.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
