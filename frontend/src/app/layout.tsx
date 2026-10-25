import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  weight: ["300", "400", "500", "600", "700"],
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
