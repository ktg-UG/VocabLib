import { GoogleSignInButton } from "@/components/GoogleSignInButton";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center px-6">
      <h1 className="text-2xl font-semibold tracking-tight">VocabLib</h1>
      <p className="mt-1 mb-8 text-sm text-ink-mute">
        学習ダッシュボード
      </p>

      <GoogleSignInButton />

      {error && (
        <p className="mt-4 rounded-lg border border-negative/30 bg-negative/5 p-3 text-xs break-words text-negative">
          {error}
        </p>
      )}

      <p className="mt-8 text-xs text-ink-weak">
        表示されるのはログインしたアカウント自身の学習データのみです。
      </p>
    </main>
  );
}
