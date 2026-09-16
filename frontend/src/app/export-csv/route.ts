import { apiFetch } from "@/lib/api";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const start = searchParams.get("start");
  const end = searchParams.get("end");
  if (!start || !end) {
    return new Response("start and end are required", { status: 400 });
  }

  const res = await apiFetch(`/account-items/export-csv/?start=${start}&end=${end}`);
  if (!res.ok) {
    return new Response(await res.text(), { status: res.status });
  }

  return new Response(res.body, {
    status: 200,
    headers: {
      "Content-Type": res.headers.get("Content-Type") ?? "text/csv",
      "Content-Disposition": res.headers.get("Content-Disposition") ?? "attachment",
    },
  });
}
