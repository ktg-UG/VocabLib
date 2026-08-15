export default function Loading() {
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">VocabLib</h1>
        <p className="text-xs text-black/50 dark:text-white/50">読み込み中...</p>
      </header>
      <div className="flex flex-col gap-8">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-20 animate-pulse rounded-xl bg-black/[0.06] dark:bg-white/[0.08]"
            />
          ))}
        </div>
        <div className="h-56 animate-pulse rounded-xl bg-black/[0.06] dark:bg-white/[0.08]" />
      </div>
    </main>
  );
}
