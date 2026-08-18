"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

/** Alterna o tema claro/escuro (classe .dark no <html>) e persiste no localStorage. */
export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("jurisight:theme", next ? "dark" : "light");
    } catch {
      /* ignora */
    }
  };

  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-[#EAEAEF] dark:border-[#26262C] bg-white dark:bg-[#17171B] px-4 py-3.5">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#EFF4FA] dark:bg-[#1A2A3C]">
          {dark ? (
            <Moon className="h-4 w-4 text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={1.8} />
          ) : (
            <Sun className="h-4 w-4 text-[#C19A2E]" strokeWidth={1.8} />
          )}
        </div>
        <div>
          <p className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "15.5px", fontWeight: 600 }}>
            Tema escuro
          </p>
          <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.8px" }}>
            {dark ? "Ativado" : "Desativado"}
          </p>
        </div>
      </div>

      <button
        role="switch"
        aria-checked={dark}
        onClick={toggle}
        className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors ${
          dark ? "bg-[#1A3A5C]" : "bg-[#CBCED4]"
        }`}
      >
        <span
          className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-sm transition-transform ${
            dark ? "translate-x-[22px]" : "translate-x-0.5"
          }`}
        />
      </button>
    </div>
  );
}
