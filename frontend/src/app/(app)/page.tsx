/** Home — entrada de consulta (Figura 2 da RFC). Tela completa: feat/home. */
export default function HomePage() {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="max-w-xl text-center">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-[#1A3A5C]">
          IA Jurídica Trabalhista
        </p>
        <h1 className="mt-3 text-3xl font-semibold text-[#0F1117]">
          Pesquisa contextual de
          <br />
          jurisprudência trabalhista
        </h1>
        <p className="mt-4 text-sm text-[#6B6B80]">
          Base do front pronta. Esta tela é um placeholder — a versão completa vem em{" "}
          <code className="rounded bg-[#ECECF0] px-1.5 py-0.5">feat/home</code>.
        </p>
      </div>
    </div>
  );
}
