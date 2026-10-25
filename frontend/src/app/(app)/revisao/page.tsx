import { Suspense } from "react";
import { EntityReviewPage } from "@/components/revisao/entity-review-page";

/** Revisão de entidades extraídas (Figura 3 da RFC). */
export default function RevisaoPage() {
  return (
    <Suspense fallback={null}>
      <EntityReviewPage />
    </Suspense>
  );
}
