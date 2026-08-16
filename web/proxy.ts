/**
 * リクエスト前に走る処理（旧 middleware.ts）
 *
 * Next.js 16 で `middleware` は非推奨になり `proxy` に改名された。
 * 機能は同じで、ファイル名とエクスポート名だけが変わっている。
 *
 * ここでやること:
 *   1. セッションCookieの更新（期限切れを自動で延長する）
 *   2. 未ログインなら /login へ飛ばす
 */
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

// デザイン検討用のモックは開発時のみ、ログイン無しで開けるようにする
// （Supabaseのセッションを用意しなくても画面を確認できるようにするため。
//   本番では /mock 自体が notFound になる）
const PUBLIC_PATHS =
  process.env.NODE_ENV === "production"
    ? ["/login", "/auth"]
    : ["/login", "/auth", "/mock"];

export async function proxy(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          for (const { name, value } of cookiesToSet) {
            request.cookies.set(name, value);
          }
          response = NextResponse.next({ request });
          for (const { name, value, options } of cookiesToSet) {
            response.cookies.set(name, value, options);
          }
        },
      },
    },
  );

  // getSession ではなく getUser を使う。
  // getSession はCookieの中身を信じるだけだが、getUser はSupabaseに問い合わせて
  // トークンが本物か検証する（改ざんされたCookieで通り抜けられない）。
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const path = request.nextUrl.pathname;
  const isPublic = PUBLIC_PATHS.some((p) => path.startsWith(p));

  if (!user && !isPublic) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  if (user && path === "/login") {
    const url = request.nextUrl.clone();
    url.pathname = "/";
    return NextResponse.redirect(url);
  }

  return response;
}

export const config = {
  // 静的アセットには走らせない（毎回Supabaseに問い合わせるのは無駄なため）
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
