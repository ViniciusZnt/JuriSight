import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { AlertCircle, ArrowLeft } from "lucide-react";

/** Casca das telas públicas (login, cadastro, recuperação e redefinição de senha): fundo, logo,
 *  título, subtítulo, cartão e, abaixo dele, o `rodape` (links entre as telas). */
export function AuthShell({
  titulo,
  subtitulo,
  rodape,
  children,
}: {
  titulo: string;
  subtitulo: string;
  rodape?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F7F7F9] dark:bg-[#0E0E11] p-6">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo.png"
            alt="JuriSight"
            className="w-12 h-12 object-contain select-none mb-3 dark:brightness-0 dark:invert"
            draggable={false}
          />
          <h1 className="text-[#0F1117] dark:text-[#ECECEF] tracking-[-0.02em]" style={{ fontSize: "22.4px", fontWeight: 600 }}>
            {titulo}
          </h1>
          <p className="text-[#6B6B80] dark:text-[#9494A2] mt-1 text-center" style={{ fontSize: "13.8px" }}>
            {subtitulo}
          </p>
        </div>

        <div className="rounded-2xl border border-[#E4E4EC] dark:border-[#26262C] bg-white dark:bg-[#17171B] p-6 shadow-[0_4px_32px_rgba(0,0,0,0.07)] dark:shadow-none">
          {children}
        </div>

        {rodape}
      </div>
    </div>
  );
}

/** Botão primário azul das telas públicas; desabilitado fica cinza. */
export function BotaoAuth({
  disabled = false,
  type = "submit",
  onClick,
  children,
}: {
  disabled?: boolean;
  type?: "submit" | "button";
  onClick?: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`mt-5 flex w-full items-center justify-center gap-2 rounded-xl py-2.5 transition-all ${
        disabled
          ? "bg-[#F0F0F4] dark:bg-[#1C1C21] text-[#C0C0D0] dark:text-[#4A4A54] cursor-not-allowed"
          : "bg-[#1A3A5C] hover:bg-[#1E4570] text-white shadow-[0_2px_14px_rgba(26,58,92,0.30)] active:scale-[0.98]"
      }`}
      style={{ fontSize: "15.5px", fontWeight: 600 }}
    >
      {children}
    </button>
  );
}

/** Link "voltar" abaixo do cartão. */
export function LinkVoltar({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center justify-center gap-1.5 w-full mt-5 text-[#6B6B80] dark:text-[#A6A6B4] hover:text-[#1A3A5C] dark:hover:text-[#8AB0DC] transition-colors"
      style={{ fontSize: "13.2px" }}
    >
      <ArrowLeft className="w-3.5 h-3.5" strokeWidth={1.8} />
      {children}
    </button>
  );
}

/** Caixa vermelha de erro no topo do formulário. */
export function CaixaErro({ children }: { children: ReactNode }) {
  return (
    <div className="mb-4 flex items-start gap-2 rounded-xl border border-[#E8C2C2] dark:border-[#4A2529] bg-[#FBF0F0] dark:bg-[#2A1517] px-3 py-2.5">
      <AlertCircle className="w-4 h-4 text-[#C44040] dark:text-[#D96B6B] mt-0.5 flex-shrink-0" strokeWidth={1.8} />
      <p className="text-[#7A1A1A] dark:text-[#E08A93]" style={{ fontSize: "13.2px" }}>{children}</p>
    </div>
  );
}

/** Painel de conclusão dentro do cartão: ícone verde, título e texto (e, se houver, o botão). */
export function PainelSucesso({
  icone: Icone,
  titulo,
  texto,
  children,
}: {
  icone: LucideIcon;
  titulo: string;
  texto: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center text-center py-2">
      <div className="w-12 h-12 rounded-xl bg-[#EDF7F2] dark:bg-[#122A1E] flex items-center justify-center mb-4">
        <Icone className="w-5 h-5 text-[#1E6B4A] dark:text-[#6FCB9A]" strokeWidth={1.8} />
      </div>
      <p className="text-[#0F1117] dark:text-[#ECECEF] mb-1.5" style={{ fontSize: "15.5px", fontWeight: 600 }}>
        {titulo}
      </p>
      <p className="text-[#6B6B80] dark:text-[#9494A2] leading-relaxed" style={{ fontSize: "13.8px" }}>
        {texto}
      </p>
      {children}
    </div>
  );
}
