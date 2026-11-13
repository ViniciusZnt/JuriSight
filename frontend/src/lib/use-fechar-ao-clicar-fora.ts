import { useEffect, useRef, type RefObject } from "react";

/** Enquanto `aberto`, chama `fechar` ao clicar fora de `ref` (e, com `comEsc`, ao apertar Esc). */
export function useFecharAoClicarFora(ref: RefObject<HTMLElement | null>, aberto: boolean, fechar: () => void, comEsc = false) {
  // Sempre o `fechar` do último render, sem refazer os listeners a cada render.
  const ultimoFechar = useRef(fechar);
  useEffect(() => {
    ultimoFechar.current = fechar;
  });

  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && ultimoFechar.current();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && ultimoFechar.current();
    document.addEventListener("mousedown", fora);
    if (comEsc) document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", esc);
    };
  }, [aberto, comEsc, ref]);
}
