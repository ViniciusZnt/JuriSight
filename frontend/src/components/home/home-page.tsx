"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { BookOpen, FileSearch, Gavel, Star, Zap, AlertCircle, X, Loader2 } from "lucide-react";
import { SearchInput, type SearchInputHandle, type SearchSubmitPayload } from "@/components/home/search-input";
import { Fa02Alert } from "@/components/home/fa02-alert";
import { Fa05Processing } from "@/components/home/fa05-processing";
import { useConversations, type ConversationSnapshot } from "@/lib/conversations";
import { useSearchSession } from "@/lib/search-session";
import { enrich, ApiError } from "@/lib/api";

// Proxy simples para "documento extenso" (RFC FA05/RNF05): acima de 8MB, mais provável ser uma
// petição longa com muitas páginas — mostra o modal de processamento enquanto aguarda o /enrich
// real (que resume o PDF em blocos via LLM antes de extrair a EstruturaArgumentativa).
const LARGE_FILE_BYTES = 8 * 1024 * 1024;

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

interface Fa02State {
  fileName: string;
  message: string;
  query: string;
  snapshot: ConversationSnapshot;
}

/** Home: entrada de consulta (RFC Figura 2). Enviar chama POST /enrich (RF02) — a IA extrai a
 *  EstruturaArgumentativa do PDF e/ou da intenção digitada — e segue para a revisão. Um PDF sem
 *  texto extraível dispara a FA02 (aviso real do backend); um arquivo grande mostra a FA05
 *  enquanto o backend resume o documento em blocos. */
export function HomePage() {
  const router = useRouter();
  const { create, setSnapshot } = useConversations();
  const { setEnrichResult } = useSearchSession();
  const searchInputRef = useRef<SearchInputHandle>(null);
  const [loading, setLoading] = useState(false);
  const [largeFileName, setLargeFileName] = useState<string | null>(null);
  const [fa02, setFa02] = useState<Fa02State | null>(null);
  const [error, setError] = useState<string | null>(null);

  // snapshot vai junto na criação da conversa — é o que a sidebar usa pra reabrir direto na
  // Revisão (com o contexto já preenchido) em vez de largar o usuário numa tela em branco.
  const goToRevisao = (query: string, hasFile: boolean, snapshot?: ConversationSnapshot) => {
    const id = create(query || "Nova pesquisa");
    if (snapshot) setSnapshot(id, snapshot);
    router.push(hasFile ? "/revisao" : "/revisao?modo=manual");
  };

  const handleSubmit = async ({ query, hasFile, file, fileName, fileBytes }: SearchSubmitPayload) => {
    setError(null);
    setFa02(null);
    setLoading(true);
    const isLarge = hasFile && (fileBytes ?? 0) > LARGE_FILE_BYTES;
    if (isLarge) setLargeFileName(fileName);

    try {
      const res = await enrich({ pdf: file, intencao: query || null });
      setEnrichResult({
        estrutura: res.estrutura,
        hasFile,
        fileName,
        pdfExtraido: res.pdf_extraido,
        aviso: res.aviso,
      });
      const snapshot: ConversationSnapshot = {
        estrutura: res.estrutura,
        hasFile,
        fileName,
        pdfExtraido: res.pdf_extraido,
        aviso: res.aviso,
        resultados: null,
      };

      if (res.pdf_extraido === false) {
        // FA02: o backend já seguiu como FA01 (a estrutura acima veio só da intenção digitada,
        // se houver) — "Continuar sem o PDF" só precisa navegar, sem chamar /enrich de novo.
        setFa02({
          fileName: fileName ?? "arquivo enviado",
          message: res.aviso ?? "Não foi possível extrair texto do PDF enviado.",
          query,
          snapshot,
        });
        return;
      }

      goToRevisao(query, hasFile, snapshot);
    } catch (err) {
      console.error("Falha em /enrich:", err);
      setError(
        err instanceof ApiError
          ? err.message
          : "Não foi possível processar a consulta. Tente novamente em instantes."
      );
    } finally {
      setLoading(false);
      setLargeFileName(null);
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
          <SearchInput ref={searchInputRef} onSubmit={handleSubmit} disabled={loading} />

          {error && (
            <div className="w-full max-w-[720px] mx-auto mt-3 flex items-start gap-2.5 rounded-xl border border-[#E8C2C2] dark:border-[#4A2529] bg-[#FBF0F0] dark:bg-[#2A1517] px-4 py-3">
              <AlertCircle className="w-4 h-4 text-[#C44040] dark:text-[#D96B6B] mt-0.5 flex-shrink-0" strokeWidth={1.8} />
              <p className="flex-1 text-[#7A1A1A] dark:text-[#E08A93]" style={{ fontSize: "13.8px" }}>
                {error}
              </p>
              <button
                onClick={() => setError(null)}
                className="text-[#C48A8A] dark:text-[#8A5E62] hover:text-[#7A1A1A] dark:hover:text-[#E08A93] transition-colors flex-shrink-0"
                aria-label="Fechar"
              >
                <X className="w-3.5 h-3.5" strokeWidth={2} />
              </button>
            </div>
          )}

          {loading && !largeFileName && (
            <div className="w-full max-w-[720px] mx-auto mt-3 flex items-start gap-2.5 rounded-xl border border-[#D0DEEE] dark:border-[#2A3A4C] bg-[#EFF4FA] dark:bg-[#1A2A3C] px-4 py-3">
              <Loader2 className="w-4 h-4 text-[#1A3A5C] dark:text-[#8AB0DC] mt-0.5 flex-shrink-0 animate-spin" strokeWidth={1.8} />
              <p className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "13.8px" }}>
                Analisando sua consulta com IA local (Ollama)… A primeira consulta do dia pode levar
                alguns minutos enquanto o modelo carrega. Não recarregue a página — isso cancela a
                requisição em andamento.
              </p>
            </div>
          )}

          {fa02 && (
            <Fa02Alert
              fileName={fa02.fileName}
              message={fa02.message}
              onRetry={() => {
                setFa02(null);
                searchInputRef.current?.clearAndReopenFile();
              }}
              onContinueWithoutFile={() => {
                const { query, snapshot } = fa02;
                setFa02(null);
                // A estrutura já veio só da intenção (RN05/FA01) — o snapshot reflete isso,
                // mesmo tendo havido uma tentativa de upload.
                goToRevisao(query, false, { ...snapshot, hasFile: false, fileName: null });
              }}
              onDismiss={() => setFa02(null)}
            />
          )}
        </div>
      </div>

      {largeFileName && <Fa05Processing fileName={largeFileName} />}

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
