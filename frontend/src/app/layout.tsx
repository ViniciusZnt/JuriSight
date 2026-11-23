import type { Metadata } from "next";
import localFont from "next/font/local";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

// Inter servida do repositório (latin, variável; licença em fonts/OFL.txt). Com next/font/google o
// build baixava a fonte do Google e quebrava quando a rede do CI falhava. É o mesmo arquivo que o
// next/font/google gerava para o subset latin.
const inter = localFont({
  src: "./fonts/inter-latin-variable.woff2",
  variable: "--font-inter",
  weight: "300 700",
  display: "swap",
});

export const metadata: Metadata = {
  title: "JuriSight",
  description: "Pesquisa contextual de jurisprudência trabalhista com IA",
};

// Aplica o tema salvo antes da pintura, evitando o flash claro→escuro no reload.
const themeInit = `try{var t=localStorage.getItem('jurisight:theme');if(t==='dark'||(!t&&matchMedia('(prefers-color-scheme: dark)').matches))document.documentElement.classList.add('dark')}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className={`${inter.variable} h-full antialiased`} suppressHydrationWarning>
      <body className="min-h-full">
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
