import { DecisionDetailPage } from "@/components/decisao/decision-detail-page";

/** Detalhe do acórdão (Figuras 6-7 da RFC). Next 16: `params` é uma Promise e precisa de await. */
export default async function DecisaoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <DecisionDetailPage decisionId={id} />;
}
