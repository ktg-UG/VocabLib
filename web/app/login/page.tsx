import { GoogleSignInButton } from "@/components/GoogleSignInButton";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center px-6">
      <h1 className="text-2xl font-bold">VocabLib</h1>
      <p className="mt-1 mb-8 text-sm text-black/60 dark:text-white/60">
        学習ダッシュボード
      </p>

      <GoogleSignInButton />

      {error && (
        <p className="mt-4 rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-xs break-words text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      <p className="mt-8 text-xs text-black/40 dark:text-white/40">
        表示されるのはログインしたアカウント自身の学習データのみです。
      </p>
    </main>
  );
}
