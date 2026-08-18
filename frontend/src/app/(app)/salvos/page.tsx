import { Bookmark } from "lucide-react";

/** Salvos — decisões marcadas pelo usuário. Sem itens até o "Salvar" ser ligado. */
export default function SalvosPage() {
  return (
    <div className="min-h-full bg-[#F7F7F9]">
      <header className="pl-20 pr-8 py-4">
        <h1 className="text-[#0F1117]" style={{ fontSize: "18px", fontWeight: 600 }}>
          Salvos
        </h1>
      </header>

      <div className="flex flex-col items-center justify-center px-8 py-24 text-center">
        <div className="w-12 h-12 rounded-xl bg-[#EFF4FA] flex items-center justify-center mb-4">
          <Bookmark className="w-5 h-5 text-[#1A3A5C]" strokeWidth={1.8} />
        </div>
        <h2 className="text-[#0F1117]" style={{ fontSize: "15px", fontWeight: 600 }}>
          Nenhuma decisão salva ainda
        </h2>
        <p className="mt-2 max-w-sm text-[#8A8A9A]" style={{ fontSize: "13px" }}>
          Ao abrir um acórdão, use <span className="text-[#1A3A5C]">Salvar</span> para guardá-lo aqui e
          consultar depois.
        </p>
      </div>
    </div>
  );
}
