import { BUSCA, type Busca } from "@/lib/cores-busca";

/** Etiqueta pequena que diz para qual busca um campo da Revisão vai (mesmas cores do guia). */
export function EtiquetaBusca({ busca }: { busca: Busca }) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-1.5 py-[1px] align-middle normal-case tracking-normal ${BUSCA[busca].etiqueta}`}
      style={{ fontSize: "11px", fontWeight: 600 }}
    >
      {BUSCA[busca].nome}
    </span>
  );
}
