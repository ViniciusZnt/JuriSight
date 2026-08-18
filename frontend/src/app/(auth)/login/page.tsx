/** Login — fora da casca autenticada (sem sidebar). Tela completa: feat/login. */
export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F7F7F9] dark:bg-[#0E0E11] p-8">
      <div className="w-full max-w-sm rounded-xl border border-[#EBEBEF] dark:border-[#26262C] bg-white dark:bg-[#17171B] p-8 text-center shadow-sm">
        <h1 className="text-2xl font-semibold text-[#0F1117] dark:text-[#ECECEF]">JuriSight</h1>
        <p className="mt-3 text-sm text-[#6B6B80] dark:text-[#A6A6B4]">
          Placeholder de login — vem em{" "}
          <code className="rounded bg-[#ECECF0] dark:bg-[#26262C] px-1.5 py-0.5">feat/login</code>.
        </p>
      </div>
    </div>
  );
}
