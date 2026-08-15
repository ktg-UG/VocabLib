/**
 * サーバー用の Supabase クライアント
 *
 * Supabase Auth のセッションは既定でブラウザの localStorage に入るが、
 * Server Component はサーバーで動くので localStorage を読めない。
 * `@supabase/ssr` を使い、セッションを Cookie に載せることで
 * 「今ログインしているのは誰か」をサーバー側から判定できるようにしている。
 */
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import { SUPABASE_ANON_KEY, SUPABASE_URL } from "./env";

export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          for (const { name, value, options } of cookiesToSet) {
            cookieStore.set(name, value, options);
          }
        } catch {
          // Server Component からは Cookie を書けない。
          // セッションの更新は proxy.ts が担当しているので、ここは無視してよい。
        }
      },
    },
  });
}
