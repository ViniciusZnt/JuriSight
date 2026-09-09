"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { BookOpen, FileSearch, Gavel, Star, Zap } from "lucide-react";
import { SearchInput, type SearchInputHandle, type SearchSubmitPayload } from "@/components/home/search-input";
import { Fa02Alert } from "@/components/home/fa02-alert";
import { AnalyzingOverlay } from "@/components/home/analyzing-overlay";
import { ErrorBanner } from "@/components/ui/error-banner";
import { useConversations } from "@/lib/conversations";
import { useConsulta } from "@/lib/consulta";
import { enrich, ApiError, type EstruturaArgumentativa } from "@/lib/api";

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

/** Home: entrada de consulta (RFC Figura 2). Enviar chama POST /enrich (RF01/RF02/RF03) — o
 *  PDF e/ou a intenção argumentativa viram a EstruturaArgumentativa revisada na próxima tela. */
export function HomePage() {
  const router = useRouter();
  const { create } = useConversations();
  const { setEnriched } = useConsulta();
  const searchInputRef = useRef<SearchInputHandle>(null);
  const [loading, setLoading] = useState<{ fileName: string | null } | null>(null);
  const [fa02, setFa02] = useState<{ fileName: string; estrutura: EstruturaArgumentativa; aviso: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastPayload, setLastPayload] = useState<SearchSubmitPayload | null>(null);

  const goToRevisao = (fileName: string | null, estrutura: EstruturaArgumentativa, hasFile: boolean) => {
    create(estrutura.tese_central || estrutura.pedido_principal || "Nova pesquisa");
    setEnriched(fileName, estrutura);
    router.push(hasFile ? "/revisao" : "/revisao?modo=manual");
  };

  const handleSubmit = async (payload: SearchSubmitPayload) => {
    setError(null);
    setFa02(null);
    setLastPayload(payload);
    setLoading({ fileName: payload.fileName });

    try {
      const response = await enrich({
        pdf: payload.file ?? undefined,
        intencao: payload.query,
      });

      if (response.pdf_extraido === false) {
        // FA02: o backend já rodou o enriquecimento só com a intenção — não precisa rechamar /enrich.
        setFa02({
          fileName: payload.fileName ?? "",
          estrutura: response.estrutura,
          aviso: response.aviso ?? "Não foi possível extrair texto do PDF enviado.",
        });
        return;
      }

      goToRevisao(payload.fileName, response.estrutura, payload.hasFile);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente."
      );
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="flex flex-col min-h-full bg-[#F7F7F9] dark:bg-[#0E0E11]">
      {/* Topbar — pl-20 abre espaço para o botão de recolher a sidebar */}
      <header className="flex items-center justify-between gap-3 pl-20 pr-4 sm:pr-8 py-4 bg-[#F7F7F9] dark:bg-[#0E0E11] sticky top-0 z-10">
        <span className="text-[#C0C0CE] dark:text-[#5E5E6A] truncate" style={{ fontSize: "14.4px" }}>
          Início
        </span>

        <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
          <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white dark:bg-[#17171B] border border-[#E0E0EA] dark:border-[#2A2A32] shadow-[0_1px_4px_rgba(0,0,0,0.04)]">
            <Star className="w-3 h-3 text-[#C19A2E]" strokeWidth={2} fill="currentColor" />
            <span className="text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>Plano Pro</span>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-full bg-white dark:bg-[#17171B] border border-[#E0E0EA] dark:border-[#2A2A32] shadow-[0_1px_4px_rgba(0,0,0,0.04)]">
            <Zap className="w-3 h-3 text-[#1A3A5C] dark:text-[#8AB0DC] flex-shrink-0" strokeWidth={2} />
            <span className="text-[#4A4A5A] dark:text-[#C4C4CE] whitespace-nowrap" style={{ fontSize: "13.2px", fontWeight: 500 }}>
              <span className="sm:hidden">47</span>
              <span className="hidden sm:inline">47 consultas restantes</span>
            </span>
          </div>
        </div>
      </header>

      {/* Hero */}
      <div className="flex flex-col items-center justify-center px-4 sm:px-8 pt-8 sm:pt-12 pb-8">
        <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#EFF4FA] dark:bg-[#1A2A3C] border border-[#D0DEEE] dark:border-[#2A3A4C] mb-6 sm:mb-8">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo.png"
            alt="JuriSight"
            className="w-4 h-4 object-contain select-none dark:brightness-0 dark:invert"
            draggable={false}
          />
          <span className="text-[#1A3A5C] dark:text-[#8AB0DC] tracking-[0.02em]" style={{ fontSize: "13.2px", fontWeight: 600 }}>
            IA Jurídica Trabalhista
          </span>
        </div>

        <h1
          className="text-center text-[#0F1117] dark:text-[#ECECEF] tracking-[-0.03em] max-w-[600px] leading-tight px-2"
          style={{ fontSize: "clamp(28px, 5vw, 41px)", fontWeight: 600 }}
        >
          Pesquisa contextual de
          <br />
          <span className="text-[#1A3A5C] dark:text-[#8AB0DC]">jurisprudência trabalhista</span>
        </h1>

        <p
          className="text-center text-[#7A7A8E] dark:text-[#9E9EAC] mt-4 max-w-[480px] leading-relaxed px-2"
          style={{ fontSize: "17.8px", fontWeight: 400 }}
        >
          Encontre decisões alinhadas à sua tese argumentativa com inteligência semântica.
          TST, TRT e STF indexados em tempo real.
        </p>

        <div className="w-full max-w-[720px] mt-8 sm:mt-10">
          <SearchInput ref={searchInputRef} onSubmit={handleSubmit} />
          {error && (
            <div className="mt-3">
              <ErrorBanner message={error} onRetry={lastPayload ? () => handleSubmit(lastPayload) : undefined} />
            </div>
          )}
          {fa02 && (
            <Fa02Alert
              fileName={fa02.fileName}
              aviso={fa02.aviso}
              onRetry={() => {
                setFa02(null);
                searchInputRef.current?.clearAndReopenFile();
              }}
              onContinueWithoutFile={() => {
                const { estrutura } = fa02;
                setFa02(null);
                goToRevisao(null, estrutura, false);
              }}
              onDismiss={() => setFa02(null)}
            />
          )}
        </div>
      </div>

      {loading && <AnalyzingOverlay fileName={loading.fileName} />}

      {/* Features */}
      <div className="px-4 sm:px-8 pb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-[880px] mx-auto">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <div
                key={feature.title}
                className="bg-white dark:bg-[#17171B] rounded-xl p-5 border border-[#EAEAEF] dark:border-[#26262C] shadow-[0_1px_6px_rgba(0,0,0,0.04)] hover:shadow-[0_2px_12px_rgba(0,0,0,0.07)] transition-all cursor-default"
              >
                <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-3" style={{ background: feature.bg }}>
                  <Icon style={{ color: feature.color, width: "18px", height: "18px" }} strokeWidth={1.8} />
                </div>
                <h3 className="text-[#0F1117] dark:text-[#ECECEF] mb-1.5" style={{ fontSize: "15.5px", fontWeight: 600 }}>
                  {feature.title}
                </h3>
                <p className="text-[#8A8A9A] dark:text-[#9494A2] leading-relaxed" style={{ fontSize: "14.4px" }}>
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
