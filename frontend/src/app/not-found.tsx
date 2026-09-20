import Link from "next/link";
import { Scale, ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#F7F7F9] dark:bg-[#0E0E11] px-6 text-center">
      <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-[#EFF4FA] dark:bg-[#1A2A3C] mb-6">
        <Scale className="w-7 h-7 text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={1.8} />
      </div>
      <p className="text-[#1A3A5C] dark:text-[#8AB0DC] tracking-[-0.02em]" style={{ fontSize: "48px", fontWeight: 700 }}>
        404
      </p>
      <h1 className="text-[#0F1117] dark:text-[#ECECEF] mt-2" style={{ fontSize: "20.7px", fontWeight: 600 }}>
        Página não encontrada
      </h1>
      <p className="text-[#8A8A9A] dark:text-[#9494A2] mt-2 max-w-sm" style={{ fontSize: "14.9px" }}>
        O endereço que você tentou acessar não existe ou foi movido.
      </p>
      <Link
        href="/"
        className="flex items-center gap-2 mt-6 px-4 py-2.5 rounded-xl bg-[#1A3A5C] text-white hover:bg-[#1E4570] active:scale-[0.98] transition-all"
        style={{ fontSize: "14.9px", fontWeight: 600 }}
      >
        <ArrowLeft className="w-4 h-4" strokeWidth={1.8} />
        Voltar para o início
      </Link>
    </main>
  );
}
