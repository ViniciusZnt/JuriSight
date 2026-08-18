"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Plus,
  MessageSquare,
  Search,
  Settings,
  Bookmark,
  MoreHorizontal,
  Pencil,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { useConversations, groupByRecency } from "@/lib/conversations";

export function Sidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const { conversations, activeId, rename, remove, setActive } = useConversations();

  const [filter, setFilter] = useState("");
  const [menuId, setMenuId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const filtered = filter.trim()
    ? conversations.filter((c) => c.title.toLowerCase().includes(filter.trim().toLowerCase()))
    : conversations;
  const groups = groupByRecency(filtered);

  const novaPesquisa = () => {
    setActive(null);
    router.push("/");
  };
  const abrir = (id: string) => {
    setActive(id);
    router.push("/resultados");
  };
  const startRename = (id: string, title: string) => {
    setMenuId(null);
    setEditingId(id);
    setDraft(title);
  };
  const commitRename = () => {
    if (editingId) rename(editingId, draft);
    setEditingId(null);
  };

  return (
    <aside className="flex flex-col h-full w-[260px] bg-white border-r border-[#EBEBEF]">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-[#EBEBEF]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/logo.png"
          alt="JuriSight"
          className="w-10 h-10 object-contain flex-shrink-0 select-none"
          draggable={false}
        />
        <span className="text-[#0F1117] tracking-[-0.01em]" style={{ fontSize: "18.4px", fontWeight: 600 }}>
          JuriSight
        </span>
      </div>

      {/* Nova pesquisa */}
      <div className="px-3 pt-4 pb-2">
        <button
          onClick={novaPesquisa}
          className="flex items-center gap-2.5 w-full rounded-lg px-3 py-2.5 bg-[#1A3A5C] text-white transition-all hover:bg-[#1E4570] active:scale-[0.98]"
        >
          <Plus className="w-4 h-4 flex-shrink-0" strokeWidth={2} />
          <span style={{ fontSize: "15.5px", fontWeight: 500 }}>Nova pesquisa</span>
        </button>
      </div>

      {/* Buscar consultas */}
      <div className="px-3 pb-2">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#F6F6F9] border border-[#EBEBEF]">
          <Search className="w-3.5 h-3.5 text-[#9B9BAD] flex-shrink-0" strokeWidth={2} />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            type="text"
            placeholder="Buscar consultas..."
            className="bg-transparent outline-none w-full text-[#6B6B80] placeholder:text-[#AEAEBF]"
            style={{ fontSize: "14.4px" }}
          />
        </div>
      </div>

      {/* Histórico */}
      <div className="flex-1 overflow-y-auto px-2 py-1 space-y-1">
        {groups.length === 0 ? (
          <p className="px-3 py-6 text-center text-[#AEAEBF]" style={{ fontSize: "13.8px" }}>
            {conversations.length === 0
              ? "Nenhuma pesquisa ainda. Comece uma nova."
              : "Nada encontrado."}
          </p>
        ) : (
          groups.map((group) => (
            <div key={group.label} className="mb-1">
              <p
                className="px-2 py-1.5 text-[#AEAEBF] uppercase tracking-[0.06em]"
                style={{ fontSize: "12.1px", fontWeight: 600 }}
              >
                {group.label}
              </p>
              {group.items.map((c) => (
                <div key={c.id} className="relative">
                  {editingId === c.id ? (
                    <input
                      autoFocus
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onBlur={commitRename}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitRename();
                        if (e.key === "Escape") setEditingId(null);
                      }}
                      className="w-full px-2 py-2 rounded-lg bg-[#F6F6F9] border border-[#1A3A5C] outline-none text-[#1A3A5C]"
                      style={{ fontSize: "14.4px" }}
                    />
                  ) : (
                    <div
                      className={`group flex items-center rounded-lg transition-all ${
                        activeId === c.id ? "bg-[#EFF4FA]" : "hover:bg-[#F6F6F9]"
                      }`}
                    >
                      <button
                        onClick={() => abrir(c.id)}
                        className="flex flex-1 items-center gap-2.5 px-2 py-2 text-left min-w-0"
                      >
                        <MessageSquare
                          className={`w-3.5 h-3.5 flex-shrink-0 ${
                            activeId === c.id ? "text-[#1A3A5C]" : "text-[#AEAEBF]"
                          }`}
                          strokeWidth={1.8}
                        />
                        <span
                          className={`flex-1 truncate ${activeId === c.id ? "text-[#1A3A5C]" : "text-[#4A4A5A]"}`}
                          style={{ fontSize: "14.4px", fontWeight: activeId === c.id ? 500 : 400 }}
                        >
                          {c.title}
                        </span>
                      </button>
                      <button
                        onClick={() => setMenuId(menuId === c.id ? null : c.id)}
                        className="px-1.5 py-2 text-[#AEAEBF] opacity-0 group-hover:opacity-100 hover:text-[#1A3A5C]"
                        title="Opções"
                      >
                        <MoreHorizontal className="w-3.5 h-3.5" strokeWidth={1.8} />
                      </button>
                    </div>
                  )}

                  {menuId === c.id && (
                    <>
                      <div className="fixed inset-0 z-40" onClick={() => setMenuId(null)} />
                      <div className="absolute right-2 top-9 z-50 w-36 rounded-lg border border-[#EAEAEF] bg-white py-1 shadow-lg">
                        <button
                          onClick={() => startRename(c.id, c.title)}
                          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[#4A4A5A] hover:bg-[#F6F6F9]"
                          style={{ fontSize: "14.4px" }}
                        >
                          <Pencil className="w-3.5 h-3.5" strokeWidth={1.8} /> Renomear
                        </button>
                        <button
                          onClick={() => {
                            remove(c.id);
                            setMenuId(null);
                          }}
                          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[#D4183D] hover:bg-[#FDF2F4]"
                          style={{ fontSize: "14.4px" }}
                        >
                          <Trash2 className="w-3.5 h-3.5" strokeWidth={1.8} /> Apagar
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          ))
        )}
      </div>

      {/* Rodapé */}
      <div className="border-t border-[#EBEBEF] px-3 py-3 space-y-1">
        <NavButton icon={Bookmark} label="Salvos" active={pathname === "/salvos"} onClick={() => router.push("/salvos")} />
        <NavButton
          icon={Settings}
          label="Configurações"
          active={pathname === "/configuracoes"}
          onClick={() => router.push("/configuracoes")}
        />

        <div className="flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-[#F6F6F9] cursor-pointer transition-all mt-1">
          <div className="w-7 h-7 rounded-full bg-[#E8EDF4] flex items-center justify-center flex-shrink-0">
            <span className="text-[#1A3A5C]" style={{ fontSize: "12.6px", fontWeight: 600 }}>
              MA
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[#0F1117] truncate" style={{ fontSize: "14.4px", fontWeight: 500 }}>
              Marcos Almeida
            </p>
            <p className="text-[#AEAEBF] truncate" style={{ fontSize: "12.6px" }}>
              Plano Pro
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}

function NavButton({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2.5 w-full px-2 py-2 rounded-lg transition-all ${
        active ? "bg-[#EFF4FA] text-[#1A3A5C]" : "text-[#6B6B80] hover:bg-[#F6F6F9]"
      }`}
    >
      <Icon className="w-3.5 h-3.5" strokeWidth={1.8} />
      <span style={{ fontSize: "14.4px" }}>{label}</span>
    </button>
  );
}
