"use client";

import { useState, useRef } from "react";
import { Paperclip, ArrowUp, FileText, X, Sparkles } from "lucide-react";

interface UploadedFile {
  name: string;
  size: string;
}

/** Campo de consulta: textarea auto-expansível + anexar PDF + enviar. */
export function SearchInput({ onSubmit }: { onSubmit?: () => void }) {
  const [query, setQuery] = useState("");
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);
  const [isFocused, setIsFocused] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleFileSelect = () => fileInputRef.current?.click();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const sizeKb = Math.round(file.size / 1024);
      const sizeStr = sizeKb > 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`;
      setUploadedFile({ name: file.name, size: sizeStr });
    }
  };

  const removeFile = () => {
    setUploadedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setQuery(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  };

  const canSubmit = query.trim().length > 0 || uploadedFile !== null;

  return (
    <div className="w-full max-w-[720px] mx-auto">
      <div
        className={`relative bg-white rounded-2xl transition-all duration-200 ${
          isFocused
            ? "shadow-[0_0_0_2px_rgba(26,58,92,0.12),0_4px_24px_rgba(26,58,92,0.08)]"
            : "shadow-[0_2px_12px_rgba(0,0,0,0.06),0_0_0_1px_rgba(0,0,0,0.06)]"
        }`}
      >
        {/* Chip do arquivo anexado */}
        {uploadedFile && (
          <div className="flex items-center gap-2 px-4 pt-3.5">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-[#EFF4FA] rounded-lg border border-[#D0DEEE]">
              <FileText className="w-3.5 h-3.5 text-[#1A3A5C]" strokeWidth={1.8} />
              <span className="text-[#1A3A5C] max-w-[200px] truncate" style={{ fontSize: "12px", fontWeight: 500 }}>
                {uploadedFile.name}
              </span>
              <span className="text-[#7A9AB8]" style={{ fontSize: "11px" }}>{uploadedFile.size}</span>
              <button onClick={removeFile} className="text-[#7A9AB8] hover:text-[#1A3A5C] transition-colors ml-0.5">
                <X className="w-3 h-3" strokeWidth={2} />
              </button>
            </div>
          </div>
        )}

        {/* Textarea */}
        <div className="px-4 pt-4 pb-2">
          <textarea
            ref={textareaRef}
            value={query}
            onChange={handleTextareaInput}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder="Descreva sua tese argumentativa ou envie os autos do processo…"
            rows={3}
            className="w-full resize-none bg-transparent outline-none text-[#0F1117] placeholder:text-[#B0B0C0] leading-relaxed"
            style={{ fontSize: "14.5px", fontWeight: 400, minHeight: "72px", maxHeight: "240px" }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (canSubmit) onSubmit?.();
              }
            }}
          />
        </div>

        {/* Barra inferior */}
        <div className="flex items-center justify-between px-3.5 pb-3.5 pt-1">
          <div className="flex items-center gap-1">
            <button
              onClick={handleFileSelect}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[#7A7A8E] hover:bg-[#F6F6F9] hover:text-[#1A3A5C] transition-all"
              title="Enviar PDF ou documento"
            >
              <Paperclip className="w-4 h-4" strokeWidth={1.8} />
              <span style={{ fontSize: "12px" }}>Anexar PDF</span>
            </button>

            <div className="w-px h-4 bg-[#E8E8EC] mx-1" />

            <button className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[#7A7A8E] hover:bg-[#F6F6F9] hover:text-[#1A3A5C] transition-all">
              <Sparkles className="w-3.5 h-3.5" strokeWidth={1.8} />
              <span style={{ fontSize: "12px" }}>Contextual</span>
            </button>
          </div>

          <div className="flex items-center gap-2">
            {query.length > 0 && (
              <span className="text-[#C0C0D0]" style={{ fontSize: "11px" }}>
                ⇧ Enter para nova linha
              </span>
            )}
            <button
              disabled={!canSubmit}
              onClick={() => canSubmit && onSubmit?.()}
              className={`flex items-center justify-center w-8 h-8 rounded-lg transition-all ${
                canSubmit
                  ? "bg-[#1A3A5C] hover:bg-[#1E4570] text-white shadow-sm active:scale-95"
                  : "bg-[#F0F0F4] text-[#C0C0D0] cursor-not-allowed"
              }`}
            >
              <ArrowUp className="w-4 h-4" strokeWidth={2.2} />
            </button>
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.doc,.docx"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>

      <p className="text-center text-[#C0C0CE] mt-3" style={{ fontSize: "11.5px" }}>
        Pressione{" "}
        <kbd className="px-1 py-0.5 rounded bg-[#EEEEF2] text-[#9090A0] border border-[#DCDCE4]" style={{ fontSize: "10.5px" }}>
          Enter
        </kbd>{" "}
        para pesquisar • Suporte a PDF, Word e texto livre
      </p>
    </div>
  );
}
