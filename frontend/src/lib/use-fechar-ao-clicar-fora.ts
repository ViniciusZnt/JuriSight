import { useEffect, useRef, type RefObject } from "react";

/** Enquanto `aberto`, chama `fechar` ao clicar fora de `ref` e, com `comEsc`, ao apertar Esc.
 *  `comEsc` pode ser uma função: aí o Esc chama ela no lugar de `fechar` (ex.: fechar e devolver
 *  o foco ao botão, o que não se quer no clique fora). */
export function useFecharAoClicarFora(
  ref: RefObject<HTMLElement | null>,
  aberto: boolean,
  fechar: () => void,
  comEsc: boolean | (() => void) = false,
) {
  // Sempre os callbacks do último render, sem refazer os listeners a cada render.
  const ultimoFechar = useRef(fechar);
  const ultimoEsc = useRef(comEsc);
  useEffect(() => {
    ultimoFechar.current = fechar;
    ultimoEsc.current = comEsc;
  });

  const escAtivo = comEsc !== false;
  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && ultimoFechar.current();
    const esc = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const aoEsc = ultimoEsc.current;
      (typeof aoEsc === "function" ? aoEsc : ultimoFechar.current)();
    };
    document.addEventListener("mousedown", fora);
    if (escAtivo) document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", esc);
    };
  }, [aberto, escAtivo, ref]);
}
