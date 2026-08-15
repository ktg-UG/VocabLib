/**
 * Supabase の接続情報
 *
 * `NEXT_PUBLIC_` が付いているのは設計どおり。`anon` キーはブラウザに出て良いキーで、
 * 実際の防御は RLS が担う（ログインボタンはブラウザ側で Supabase Auth を呼ぶため、
 * ブラウザから見える必要がある）。
 *
 * `service_role` キーはここには絶対に置かない。Phase 6 以降、Web は一切使わない。
 */
export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
  throw new Error(
    "NEXT_PUBLIC_SUPABASE_URL と NEXT_PUBLIC_SUPABASE_ANON_KEY を web/.env.local に設定してください",
  );
}
