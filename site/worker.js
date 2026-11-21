// Serves the public podcast files (docs/) and supports partial downloads (HTTP Range),
// which Apple Podcasts requires for streaming.
export default {
  async fetch(request, env) {
    const res = await env.ASSETS.fetch(request);
    const range = request.headers.get("Range");
    if (!range || res.status !== 200) return res;
    const m = /^bytes=(\d*)-(\d*)$/.exec(range.trim());
    if (!m) return res;
    const body = await res.arrayBuffer();
    const size = body.byteLength;
    let start = m[1] === "" ? size - Number(m[2]) : Number(m[1]);
    let end = m[1] !== "" && m[2] !== "" ? Number(m[2]) : size - 1;
    end = Math.min(end, size - 1);
    if (isNaN(start) || start < 0 || start > end) {
      return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${size}` } });
    }
    const headers = new Headers(res.headers);
    headers.set("Content-Range", `bytes ${start}-${end}/${size}`);
    headers.set("Content-Length", String(end - start + 1));
    headers.set("Accept-Ranges", "bytes");
    return new Response(body.slice(start, end + 1), { status: 206, headers });
  },
};
