import Link from "next/link";
import { BookOpen } from "lucide-react";

/** Acesso ao guia de uso, no canto do topo da tela inicial. */
export function ComoUsarLink() {
  return (
    <Link
      href="/guia"
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 border border-[#D0DEEE] dark:border-[#2A3A4C] bg-white dark:bg-[#17171B] text-[#1A3A5C] dark:text-[#8AB0DC] hover:border-[#1A3A5C] dark:hover:border-[#8AB0DC] transition-colors flex-shrink-0"
      style={{ fontSize: "13.2px", fontWeight: 600 }}
    >
      <BookOpen aria-hidden="true" className="w-4 h-4" strokeWidth={2} />
      Como usar
    </Link>
  );
}
