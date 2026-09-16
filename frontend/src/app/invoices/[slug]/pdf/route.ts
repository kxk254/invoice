import { apiFetch } from "@/lib/api";

export async function GET(request: Request, ctx: RouteContext<"/invoices/[slug]/pdf">) {
  const { slug } = await ctx.params;
  const download = new URL(request.url).searchParams.get("download");
  const query = download ? "?download=1" : "";

  const res = await apiFetch(`/invoices/${encodeURIComponent(slug)}/pdf/${query}`);
  if (!res.ok) {
    return new Response(await res.text(), { status: res.status });
  }

  return new Response(res.body, {
    status: 200,
    headers: {
      "Content-Type": res.headers.get("Content-Type") ?? "application/pdf",
      "Content-Disposition": res.headers.get("Content-Disposition") ?? "inline",
    },
  });
}
