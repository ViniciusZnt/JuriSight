import { renderHook, act, waitFor } from "@testing-library/react";
import { SavedProvider, useSaved, type SavedDecision } from "@/lib/saved";

const sample: Omit<SavedDecision, "savedAt"> = {
  id: "1",
  title: "Adicional de insalubridade — exposição a agentes químicos cancerígenos",
  court: "TST",
  chamber: "3ª Turma",
  date: "2025-04-28",
  outcome: "favorable",
  relevance: 98,
  rapporteur: "Min. Alberto Bresciani",
  processNumber: "TST-RR-100-44.2021.5.01.0019",
};

beforeEach(() => {
  window.localStorage.clear();
});

describe("useSaved", () => {
  it("começa vazio quando não há nada salvo", async () => {
    const { result } = renderHook(() => useSaved(), { wrapper: SavedProvider });
    await waitFor(() => expect(result.current.isSaved("1")).toBe(false));
    expect(result.current.saved).toHaveLength(0);
  });

  it("toggle salva a decisão e marca isSaved como true", async () => {
    const { result } = renderHook(() => useSaved(), { wrapper: SavedProvider });
    await waitFor(() => expect(result.current.isSaved("1")).toBe(false));

    act(() => result.current.toggle(sample));

    expect(result.current.isSaved("1")).toBe(true);
    expect(result.current.saved).toHaveLength(1);
    expect(result.current.saved[0].title).toBe(sample.title);
  });

  it("toggle de novo remove a decisão salva", async () => {
    const { result } = renderHook(() => useSaved(), { wrapper: SavedProvider });
    await waitFor(() => expect(result.current.isSaved("1")).toBe(false));

    act(() => result.current.toggle(sample));
    expect(result.current.isSaved("1")).toBe(true);

    act(() => result.current.toggle(sample));
    expect(result.current.isSaved("1")).toBe(false);
    expect(result.current.saved).toHaveLength(0);
  });

  it("persiste no localStorage entre instâncias do provider", async () => {
    const first = renderHook(() => useSaved(), { wrapper: SavedProvider });
    await waitFor(() => expect(first.result.current.isSaved("1")).toBe(false));
    act(() => first.result.current.toggle(sample));
    first.unmount();

    const second = renderHook(() => useSaved(), { wrapper: SavedProvider });
    await waitFor(() => expect(second.result.current.saved).toHaveLength(1));
    expect(second.result.current.isSaved("1")).toBe(true);
  });

  it("lança um erro claro quando usado fora do SavedProvider", () => {
    const spy = jest.spyOn(console, "error").mockImplementation(() => {});
    expect(() => renderHook(() => useSaved())).toThrow("useSaved precisa de <SavedProvider>.");
    spy.mockRestore();
  });
});
