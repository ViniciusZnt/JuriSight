import { useState } from "react";
import { copiarTexto } from "@/lib/utils";

/** `[copiado, copiar]`: copia o texto e deixa `copiado` verdadeiro por 2 s, para o botão mostrar "Copiado!". */
export function useCopiar(): [boolean, (texto: string) => Promise<void>] {
  const [copiado, setCopiado] = useState(false);
  const copiar = async (texto: string) => {
    await copiarTexto(texto);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 2000);
  };
  return [copiado, copiar];
}
