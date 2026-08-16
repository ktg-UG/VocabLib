export default function Loading() {
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">VocabLib</h1>
        <p className="text-xs text-ink-weak">読み込み中...</p>
      </header>
      <div className="flex flex-col gap-8">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-20 animate-pulse rounded-lg bg-border"
            />
          ))}
        </div>
        <div className="h-56 animate-pulse rounded-lg bg-border" />
      </div>
    </main>
  );
}
