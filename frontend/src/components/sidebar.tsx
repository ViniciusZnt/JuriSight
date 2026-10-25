"use client";

import { useState } from "react";
import {
  Plus,
  MessageSquare,
  Search,
  Settings,
  Bookmark,
  MoreHorizontal,
} from "lucide-react";

interface HistoryItem {
  id: string;
  title: string;
  date: string;
  category: string;
}

// Dados mock — a listagem real do histórico entra numa feature branch.
const historyGroups: { label: string; items: HistoryItem[] }[] = [
  {
    label: "Hoje",
    items: [
      { id: "1", title: "Insalubridade por exposição a benzeno", date: "14:32", category: "NR-15" },
      { id: "2", title: "Horas extras bancário — jornada 6h", date: "11:15", category: "CLT 224" },
    ],
  },
  {
    label: "Ontem",
    items: [
      { id: "3", title: "Periculosidade com inflamáveis", date: "16:44", category: "NR-16" },
      { id: "4", title: "NR-15 sem fornecimento de EPI", date: "09:20", category: "NR-15" },
    ],
  },
  {
    label: "Esta semana",
    items: [
      { id: "5", title: "Responsabilidade subsidiária terceirização", date: "Ter", category: "Súmula 331" },
      { id: "6", title: "Equiparação salarial — requisitos", date: "Ter", category: "CLT 461" },
      { id: "7", title: "Assédio moral — dano existencial", date: "Seg", category: "TST" },
    ],
  },
];

export function Sidebar({ collapsed = false }: { collapsed?: boolean }) {
  const [activeId, setActiveId] = useState("1");
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  return (
    <aside
      className={`flex flex-col h-full bg-white border-r border-[#EBEBEF] transition-all duration-300 ${
        collapsed ? "w-[64px]" : "w-[260px]"
      }`}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-4 border-b border-[#EBEBEF]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/logo.png"
          alt="JuriSight"
          className="w-8 h-8 object-contain flex-shrink-0 select-none"
          draggable={false}
        />
        {!collapsed && (
          <span className="text-[#0F1117] tracking-[-0.01em]" style={{ fontSize: "15px", fontWeight: 600 }}>
            JuriSight
          </span>
        )}
      </div>

      {/* Nova pesquisa */}
      <div className="px-3 pt-4 pb-2">
        <button
          className={`flex items-center gap-2.5 w-full rounded-lg px-3 py-2.5 bg-[#1A3A5C] text-white transition-all hover:bg-[#1E4570] active:scale-[0.98] ${
            collapsed ? "justify-center" : ""
          }`}
        >
          <Plus className="w-4 h-4 flex-shrink-0" strokeWidth={2} />
          {!collapsed && <span style={{ fontSize: "13.5px", fontWeight: 500 }}>Nova pesquisa</span>}
        </button>
      </div>

      {/* Busca de consultas */}
      {!collapsed && (
        <div className="px-3 pb-2">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#F6F6F9] border border-[#EBEBEF]">
            <Search className="w-3.5 h-3.5 text-[#9B9BAD] flex-shrink-0" strokeWidth={2} />
            <input
              type="text"
              placeholder="Buscar consultas..."
              className="bg-transparent outline-none w-full text-[#6B6B80] placeholder:text-[#AEAEBF]"
              style={{ fontSize: "12.5px" }}
            />
          </div>
        </div>
      )}

      {/* Histórico */}
      <div className="flex-1 overflow-y-auto px-2 py-1 space-y-1">
        {historyGroups.map((group) => (
          <div key={group.label} className="mb-1">
            {!collapsed && (
              <p
                className="px-2 py-1.5 text-[#AEAEBF] uppercase tracking-[0.06em]"
                style={{ fontSize: "10.5px", fontWeight: 600 }}
              >
                {group.label}
              </p>
            )}
            {group.items.map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveId(item.id)}
                onMouseEnter={() => setHoveredId(item.id)}
                onMouseLeave={() => setHoveredId(null)}
                className={`w-full flex items-center gap-2.5 px-2 py-2 rounded-lg transition-all text-left group relative ${
                  activeId === item.id ? "bg-[#EFF4FA] text-[#1A3A5C]" : "text-[#4A4A5A] hover:bg-[#F6F6F9]"
                } ${collapsed ? "justify-center" : ""}`}
              >
                <MessageSquare
                  className={`w-3.5 h-3.5 flex-shrink-0 ${
                    activeId === item.id ? "text-[#1A3A5C]" : "text-[#AEAEBF]"
                  }`}
                  strokeWidth={1.8}
                />
                {!collapsed && (
                  <span
                    className="flex-1 truncate"
                    style={{ fontSize: "12.5px", fontWeight: activeId === item.id ? 500 : 400 }}
                  >
                    {item.title}
                  </span>
                )}
                {!collapsed && hoveredId === item.id && (
                  <MoreHorizontal
                    className="w-3.5 h-3.5 text-[#AEAEBF] flex-shrink-0 opacity-0 group-hover:opacity-100"
                    strokeWidth={1.8}
                  />
                )}
              </button>
            ))}
          </div>
        ))}
      </div>

      {/* Rodapé */}
      <div className="border-t border-[#EBEBEF] px-3 py-3 space-y-1">
        <button
          className={`flex items-center gap-2.5 w-full px-2 py-2 rounded-lg text-[#6B6B80] hover:bg-[#F6F6F9] transition-all ${
            collapsed ? "justify-center" : ""
          }`}
        >
          <Bookmark className="w-3.5 h-3.5" strokeWidth={1.8} />
          {!collapsed && <span style={{ fontSize: "12.5px" }}>Salvos</span>}
        </button>
        <button
          className={`flex items-center gap-2.5 w-full px-2 py-2 rounded-lg text-[#6B6B80] hover:bg-[#F6F6F9] transition-all ${
            collapsed ? "justify-center" : ""
          }`}
        >
          <Settings className="w-3.5 h-3.5" strokeWidth={1.8} />
          {!collapsed && <span style={{ fontSize: "12.5px" }}>Configurações</span>}
        </button>

        {/* Usuário */}
        <div
          className={`flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-[#F6F6F9] cursor-pointer transition-all mt-1 ${
            collapsed ? "justify-center" : ""
          }`}
        >
          <div className="w-7 h-7 rounded-full bg-[#E8EDF4] flex items-center justify-center flex-shrink-0">
            <span className="text-[#1A3A5C]" style={{ fontSize: "11px", fontWeight: 600 }}>
              MA
            </span>
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-[#0F1117] truncate" style={{ fontSize: "12.5px", fontWeight: 500 }}>
                Marcos Almeida
              </p>
              <p className="text-[#AEAEBF] truncate" style={{ fontSize: "11px" }}>
                Plano Pro
              </p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
