const FORWARDED_HEADERS = new Set([
  'accept', 'accept-language', 'content-type', 'cookie', 'origin', 'referer',
  'user-agent', 'x-csrftoken',
]);

export async function proxyToRender(request, response, prefix) {
  const origin = (process.env.RENDER_API_ORIGIN || '').replace(/\/+$/, '');
  if (!/^https:\/\/[^/]+$/.test(origin)) {
    response.status(503).json({ detail: 'The API proxy is not configured.' });
    return;
  }
  const pathParts = Array.isArray(request.query.path)
    ? request.query.path
    : [request.query.path || ''];
  const query = new URLSearchParams();
  Object.entries(request.query).forEach(([key, value]) => {
    if (key === 'path') return;
    for (const item of Array.isArray(value) ? value : [value]) query.append(key, item);
  });
  const target = `${origin}/${prefix}/${pathParts.map(encodeURIComponent).join('/')}${query.size ? `?${query}` : ''}`;
  const headers = {};
  Object.entries(request.headers).forEach(([key, value]) => {
    if (FORWARDED_HEADERS.has(key.toLowerCase()) && value) headers[key] = value;
  });
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  const body = ['GET', 'HEAD'].includes(request.method) ? undefined : Buffer.concat(chunks);
  const upstream = await fetch(target, { method: request.method, headers, body, redirect: 'manual' });
  upstream.headers.forEach((value, key) => {
    if (!['content-length', 'content-encoding', 'transfer-encoding', 'set-cookie'].includes(key.toLowerCase())) response.setHeader(key, value);
  });
  if (typeof upstream.headers.getSetCookie === 'function') {
    const cookies = upstream.headers.getSetCookie();
    if (cookies.length) response.setHeader('set-cookie', cookies);
  } else if (upstream.headers.get('set-cookie')) {
    response.setHeader('set-cookie', upstream.headers.get('set-cookie'));
  }
  response.status(upstream.status).send(Buffer.from(await upstream.arrayBuffer()));
}
