import { NextRequest, NextResponse } from "next/server";

// Server-side proxy for the backend's internal-token-guarded observability
// endpoints. The browser never sees INTERNAL_OBSERVABILITY_TOKEN: it stays in
// this server-only handler. The caller's JWT is forwarded from the incoming
// Authorization header (the backend still enforces get_current_user). GET-only
// — these are read-only metrics surfaces.

// Server-side base URL: inside Compose the frontend reaches the API by service
// name (http://backend:8000); on host it's 127.0.0.1:8000. Never NEXT_PUBLIC —
// this resolves server-side only.
const BACKEND_BASE_URL =
  process.env.BACKEND_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

export async function GET(
  req: NextRequest,
  { params }: { params: { path: string[] } },
) {
  const token = process.env.INTERNAL_OBSERVABILITY_TOKEN;
  if (!token) {
    return NextResponse.json(
      { detail: "Observability dashboard is not configured (missing internal token)." },
      { status: 503 },
    );
  }

  const auth = req.headers.get("authorization");
  if (!auth) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const subPath = (params.path ?? []).join("/");
  const search = req.nextUrl.search; // preserves ?window=30d etc.
  const target = `${BACKEND_BASE_URL}/observability/${subPath}${search}`;

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: "GET",
      headers: {
        Authorization: auth,
        "x-internal-token": token,
        Accept: "application/json",
      },
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "Upstream observability API unreachable" }, { status: 502 });
  }

  const body = await upstream.text();
  return new NextResponse(body, {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
  });
}
