import { useEffect, type RefObject } from "react";

/** Enquanto `aberto`, chama `fechar` ao clicar fora de `ref` (e, com `comEsc`, ao apertar Esc). */
export function useFecharAoClicarFora(ref: RefObject<HTMLElement | null>, aberto: boolean, fechar: () => void, comEsc = false) {
  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && fechar();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && fechar();
    document.addEventListener("mousedown", fora);
    if (comEsc) document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", esc);
    };
    // `fechar` costuma ser uma função nova a cada render; o efeito só precisa refazer quando abre/fecha.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aberto, comEsc, ref]);
}
