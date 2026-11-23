import { copiarTexto } from "@/lib/utils";

describe("copiarTexto", () => {
  const original = navigator.clipboard;
  afterEach(() => Object.defineProperty(navigator, "clipboard", { configurable: true, value: original }));
  const clipboard = (valor: unknown) => Object.defineProperty(navigator, "clipboard", { configurable: true, value: valor });

  it("usa a Clipboard API quando existe", async () => {
    const writeText = jest.fn().mockResolvedValue(undefined);
    clipboard({ writeText });
    await copiarTexto("abc");
    expect(writeText).toHaveBeenCalledWith("abc");
  });

  it("sem Clipboard API, cai no execCommand com um textarea temporário", async () => {
    clipboard(undefined);
    const exec = jest.fn();
    Object.defineProperty(document, "execCommand", { configurable: true, value: exec });
    await copiarTexto("xyz");
    expect(exec).toHaveBeenCalledWith("copy");
    expect(document.querySelector("textarea")).toBeNull();
  });

  it("se nem o execCommand funciona, não quebra", async () => {
    clipboard({ writeText: () => Promise.reject(new Error("negado")) });
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: () => {
        throw new Error("sem suporte");
      },
    });
    await expect(copiarTexto("x")).resolves.toBeUndefined();
    expect(document.querySelector("textarea")).toBeNull();
  });
});
