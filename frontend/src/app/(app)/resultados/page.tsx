/** Resultados da busca (Figuras 4-5 da RFC). Tela completa: feat/search-results. */
export default function SearchResultsPage() {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="text-center">
        <h1 className="text-2xl font-semibold text-[#0F1117] dark:text-[#ECECEF]">Jurisprudências</h1>
        <p className="mt-3 text-sm text-[#6B6B80] dark:text-[#A6A6B4]">
          Placeholder — vem em{" "}
          <code className="rounded bg-[#ECECF0] dark:bg-[#26262C] px-1.5 py-0.5">feat/search-results</code>.
        </p>
      </div>
    </div>
  );
}
