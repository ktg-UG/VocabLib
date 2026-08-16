import Link from "next/link";

/**
 * ページの外枠（ヘッダー・ナビ・ログアウト）
 *
 * ダッシュボードと単語一覧で共有する。片方だけヘッダーが変わると
 * 「別のアプリに飛んだ」ように見えるため、1箇所にまとめる。
 */
export function Shell({
  children,
  email,
  current,
  base = "",
}: {
  children: React.ReactNode;
  email?: string;
  current: "dashboard" | "words" | "study" | "new";
  /** モック（/mock）から使うときのプレフィックス。本番は空 */
  base?: string;
}) {
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">VocabLib</h1>
          <p className="mt-0.5 text-xs text-ink-weak">
            {email ?? "英単語学習"}
          </p>
        </div>
        <form action="/auth/signout" method="post">
          <button
            type="submit"
            className="rounded-md px-2 py-1 text-xs text-ink-weak transition hover:bg-accent-weak hover:text-ink-mute"
          >
            ログアウト
          </button>
        </form>
      </header>

      {/* タブ。下線1本だけで現在地を示す（枠で囲むと見出しと競合する） */}
      <nav className="mb-8 flex gap-5 border-b border-border text-sm">
        <Tab
          href={base || "/"}
          label="ダッシュボード"
          active={current === "dashboard"}
        />
        <Tab href={`${base}/words`} label="単語" active={current === "words"} />
        <Tab href={`${base}/study`} label="学習" active={current === "study"} />
        <Tab href={`${base}/new`} label="追加" active={current === "new"} />
      </nav>

      <div className="flex flex-col gap-10">{children}</div>
    </main>
  );
}

function Tab({
  href,
  label,
  active,
}: {
  href: string;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={`-mb-px border-b-2 pb-2 transition ${
        active
          ? "border-accent font-semibold text-ink"
          : "border-transparent text-ink-mute hover:text-ink"
      }`}
    >
      {label}
    </Link>
  );
}

export function Section({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="mb-3 flex items-baseline gap-2 text-[15px] font-semibold">
        {title}
        {note && <span className="text-xs font-normal text-ink-weak">{note}</span>}
      </h2>
      {children}
    </section>
  );
}

export function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-negative/30 bg-negative/5 p-4">
      <p className="text-sm font-semibold text-negative">
        データを取得できませんでした
      </p>
      <p className="mt-1 text-xs break-words text-ink-mute">{message}</p>
    </div>
  );
}
