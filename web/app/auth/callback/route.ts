/**
 * OAuth の戻り先
 *
 * Google → Supabase → **ここ** という流れの最後。
 * Supabase から渡された認可コードを、セッション（Cookie）に交換する。
 *
 * このURLは Supabase の Authentication → URL Configuration の
 * Redirect URLs に登録されている必要がある。
 */
import { NextResponse } from "next/server";

import { createClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/";

  if (!code) {
    return NextResponse.redirect(`${origin}/login?error=missing_code`);
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    return NextResponse.redirect(
      `${origin}/login?error=${encodeURIComponent(error.message)}`,
    );
  }

  return NextResponse.redirect(`${origin}${next}`);
}
