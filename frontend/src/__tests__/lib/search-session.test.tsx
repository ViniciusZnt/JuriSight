import { act, render, renderHook } from "@testing-library/react";
import { SearchSessionProvider, useSearchSession } from "@/lib/search-session";
import { emptyEstrutura, type ResultCard } from "@/lib/api";
import type { ConversationVersion } from "@/lib/conversations";

const wrapper = ({ children }: { children: React.ReactNode }) => <SearchSessionProvider>{children}</SearchSessionProvider>;
const estrutura = { ...emptyEstrutura(), tese_central: "tese" };

describe("SearchSession", () => {
  it("começa vazia", () => {
    const { result } = renderHook(useSearchSession, { wrapper });
    expect(result.current.estrutura).toBeNull();
    expect(result.current.resultados).toBeNull();
    expect(result.current.versionNumero).toBeNull();
  });

  it("setEnrichResult guarda o /enrich, zera resultados e versão, e preenche listas ausentes", () => {
    const { result } = renderHook(useSearchSession, { wrapper });
    act(() => result.current.loadVersion(versao()));
    act(() => result.current.setEnrichResult({ estrutura, hasFile: true, fileName: "a.pdf", pdfExtraido: true, aviso: null }));
    expect(result.current).toMatchObject({
      estrutura, hasFile: true, fileName: "a.pdf", resultados: null, versionNumero: null,
      dispositivosIa: [], expressoesSugeridas: [], dispositivosSugeridos: [],
    });
    act(() => result.current.setEnrichResult({ estrutura, hasFile: false, fileName: null, pdfExtraido: null, aviso: "x", dispositivosIa: ["clt_art_59"] }));
    expect(result.current.dispositivosIa).toEqual(["clt_art_59"]);
  });

  const versao = (extra: Partial<ConversationVersion> = {}): ConversationVersion => ({
    numero: 2, estrutura: { tese_central: "antiga" } as ConversationVersion["estrutura"], hasFile: false, fileName: null,
    pdfExtraido: null, aviso: null, resultados: [{ id: "r1" } as ResultCard], createdAt: 0,
    relevantesUsuario: ["r1"], respostaIds: ["r1"], ...extra,
  });

  it("loadVersion completa campos de versões antigas e respeita buscaNova", () => {
    const { result } = renderHook(useSearchSession, { wrapper });
    act(() => result.current.loadVersion(versao()));
    expect(result.current.estrutura).toEqual({ ...emptyEstrutura(), tese_central: "antiga" });
    expect(result.current).toMatchObject({ versionNumero: 2, buscaNova: false, relevantesUsuario: ["r1"], respostaIds: ["r1"] });

    act(() => result.current.loadVersion(versao({ relevantesUsuario: undefined, respostaIds: undefined } as never), { buscaNova: true }));
    expect(result.current).toMatchObject({ buscaNova: true, relevantesUsuario: [], respostaIds: [] });
  });

  it("setters e reset", () => {
    const { result } = renderHook(useSearchSession, { wrapper });
    act(() => result.current.setEstrutura(estrutura));
    act(() => result.current.setRelevantesUsuario(["a"]));
    act(() => result.current.setRespostaIds(["b"]));
    expect(result.current).toMatchObject({ estrutura, relevantesUsuario: ["a"], respostaIds: ["b"] });
    act(() => result.current.reset());
    expect(result.current).toMatchObject({ estrutura: null, relevantesUsuario: [], respostaIds: [] });
  });

  it("fora do provider avisa", () => {
    jest.spyOn(console, "error").mockImplementation(() => {});
    function Sem() {
      useSearchSession();
      return null;
    }
    expect(() => render(<Sem />)).toThrow("useSearchSession precisa de <SearchSessionProvider>.");
  });
});
