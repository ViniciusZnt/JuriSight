"use client";

import { useState, useRef, forwardRef, useImperativeHandle } from "react";
import { Paperclip, ArrowUp, FileText, X, Sparkles, Loader2 } from "lucide-react";

interface UploadedFile {
  file: File;
  name: string;
  size: string;
  bytes: number;
}

export interface SearchSubmitPayload {
  query: string;
  hasFile: boolean;
  file: File | null;
  fileName: string | null;
  fileBytes: number | null;
}

export interface SearchInputHandle {
  /** Remove o arquivo anexado e reabre o seletor — usado pelo alerta da FA02 ("Reenviar arquivo"). */
  clearAndReopenFile: () => void;
}

/** Campo de consulta: textarea auto-expansível + anexar PDF + enviar.
 *  onSubmit recebe a consulta e o PDF anexado (UC01 vs UC02), enviados à API via POST /enrich. */
export const SearchInput = forwardRef<
  SearchInputHandle,
  { onSubmit?: (payload: SearchSubmitPayload) => void; disabled?: boolean }
>(function SearchInput({ onSubmit, disabled = false }, ref) {
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
        setUploadedFile({ file, name: file.name, size: sizeStr, bytes: file.size });
      }
    };

    const removeFile = () => {
      setUploadedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    };

    useImperativeHandle(ref, () => ({
      clearAndReopenFile: () => {
        removeFile();
        fileInputRef.current?.click();
      },
    }));

    const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setQuery(e.target.value);
      const el = e.target;
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
    };

    const canSubmit = (query.trim().length > 0 || uploadedFile !== null) && !disabled;
    const submit = () => {
      if (!canSubmit) return;
      onSubmit?.({
        query: query.trim() || uploadedFile?.name || "",
        hasFile: uploadedFile !== null,
        file: uploadedFile?.file ?? null,
        fileName: uploadedFile?.name ?? null,
        fileBytes: uploadedFile?.bytes ?? null,
      });
    };

    return (
      <div className="w-full max-w-[720px] mx-auto">
        <div
          className={`relative bg-white dark:bg-[#17171B] rounded-2xl transition-all duration-200 ${
            isFocused
              ? "shadow-[0_0_0_2px_rgba(26,58,92,0.12),0_4px_24px_rgba(26,58,92,0.08)]"
              : "shadow-[0_2px_12px_rgba(0,0,0,0.06),0_0_0_1px_rgba(0,0,0,0.06)]"
          }`}
        >
          {/* Chip do arquivo anexado */}
          {uploadedFile && (
            <div className="flex items-center gap-2 px-4 pt-3.5">
              <div className="flex items-center gap-2 px-3 py-1.5 bg-[#EFF4FA] dark:bg-[#1A2A3C] rounded-lg border border-[#D0DEEE] dark:border-[#2A3A4C]">
                <FileText className="w-3.5 h-3.5 text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={1.8} />
                <span className="text-[#1A3A5C] dark:text-[#8AB0DC] max-w-[200px] truncate" style={{ fontSize: "13.8px", fontWeight: 500 }}>
                  {uploadedFile.name}
                </span>
                <span className="text-[#7A9AB8]" style={{ fontSize: "12.6px" }}>{uploadedFile.size}</span>
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
              disabled={disabled}
              placeholder="Descreva sua tese argumentativa ou envie os autos do processo…"
              rows={3}
              className="w-full resize-none bg-transparent outline-none text-[#0F1117] dark:text-[#ECECEF] placeholder:text-[#B0B0C0] leading-relaxed disabled:opacity-60"
              style={{ fontSize: "16.7px", fontWeight: 400, minHeight: "72px", maxHeight: "240px" }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
            />
          </div>

          {/* Barra inferior */}
          <div className="flex items-center justify-between px-3.5 pb-3.5 pt-1">
            <div className="flex items-center gap-1">
              <button
                onClick={handleFileSelect}
                disabled={disabled}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[#7A7A8E] dark:text-[#9E9EAC] hover:bg-[#F6F6F9] hover:text-[#1A3A5C] transition-all disabled:opacity-50 disabled:pointer-events-none"
                title="Enviar PDF"
              >
                <Paperclip className="w-4 h-4" strokeWidth={1.8} />
                <span style={{ fontSize: "13.8px" }}>Anexar PDF</span>
              </button>

              <div className="w-px h-4 bg-[#E8E8EC] mx-1" />

              <button
                disabled={disabled}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[#7A7A8E] dark:text-[#9E9EAC] hover:bg-[#F6F6F9] hover:text-[#1A3A5C] transition-all disabled:opacity-50 disabled:pointer-events-none"
              >
                <Sparkles className="w-3.5 h-3.5" strokeWidth={1.8} />
                <span style={{ fontSize: "13.8px" }}>Contextual</span>
              </button>
            </div>

            <div className="flex items-center gap-2">
              {query.length > 0 && (
                <span className="text-[#C0C0D0]" style={{ fontSize: "12.6px" }}>
                  ⇧ Enter para nova linha
                </span>
              )}
              <button
                disabled={!canSubmit}
                onClick={submit}
                className={`flex items-center justify-center w-8 h-8 rounded-lg transition-all ${
                  canSubmit
                    ? "bg-[#1A3A5C] hover:bg-[#1E4570] text-white shadow-sm active:scale-95"
                    : "bg-[#F0F0F4] text-[#C0C0D0] cursor-not-allowed"
                }`}
              >
                {disabled ? (
                  <Loader2 className="w-4 h-4 animate-spin" strokeWidth={2.2} />
                ) : (
                  <ArrowUp className="w-4 h-4" strokeWidth={2.2} />
                )}
              </button>
            </div>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={handleFileChange}
          />
        </div>

        <p className="text-center text-[#C0C0CE] dark:text-[#5E5E6A] mt-3" style={{ fontSize: "13.2px" }}>
          Pressione{" "}
          <kbd className="px-1 py-0.5 rounded bg-[#EEEEF2] dark:bg-[#26262C] text-[#9090A0] dark:text-[#7C7C88] border border-[#DCDCE4] dark:border-[#2A2A32]" style={{ fontSize: "12.1px" }}>
            Enter
          </kbd>{" "}
          para pesquisar • Suporte a PDF ou texto livre
        </p>
      </div>
    );
  }
);
