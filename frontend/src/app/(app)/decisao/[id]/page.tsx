/** Detalhe do acórdão (Figuras 6-7 da RFC). Tela completa: feat/decision-detail.
 *  Next 16: `params` é uma Promise e precisa de await. */
export default async function DecisionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="text-center">
        <h1 className="text-2xl font-semibold text-[#0F1117] dark:text-[#ECECEF]">Decisão</h1>
        <p className="mt-2 text-sm text-[#6B6B80] dark:text-[#A6A6B4]">
          documento_id: <code className="rounded bg-[#ECECF0] dark:bg-[#26262C] px-1.5 py-0.5">{id}</code>
        </p>
        <p className="mt-3 text-sm text-[#6B6B80] dark:text-[#A6A6B4]">
          Placeholder — vem em{" "}
          <code className="rounded bg-[#ECECF0] dark:bg-[#26262C] px-1.5 py-0.5">feat/decision-detail</code>.
        </p>
      </div>
    </div>
  );
}
