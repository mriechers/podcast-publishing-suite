// Cloudflare Pages Function — proxies Unsplash API requests
// The UNSPLASH_KEY is set as an environment secret in the Pages dashboard.

export async function onRequest(context) {
  const url = new URL(context.request.url);
  const action = url.searchParams.get('action');
  const key = context.env.UNSPLASH_KEY;

  if (!key) {
    return new Response(JSON.stringify({ error: 'UNSPLASH_KEY not configured' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Search photos
  if (action === 'search') {
    const query = url.searchParams.get('query');
    const page = url.searchParams.get('page') || '1';
    const perPage = url.searchParams.get('per_page') || '20';
    const orientation = url.searchParams.get('orientation') || 'squarish';

    const apiUrl = `https://api.unsplash.com/search/photos?query=${encodeURIComponent(query)}&page=${page}&per_page=${perPage}&orientation=${orientation}`;
    const resp = await fetch(apiUrl, {
      headers: { 'Authorization': `Client-ID ${key}` }
    });
    const data = await resp.text();
    return new Response(data, {
      status: resp.status,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Track download (required by Unsplash API guidelines)
  if (action === 'track-download') {
    const downloadUrl = url.searchParams.get('url');
    if (downloadUrl) {
      await fetch(`${downloadUrl}?client_id=${key}`).catch(() => {});
    }
    return new Response('ok', { status: 200 });
  }

  return new Response(JSON.stringify({ error: 'Unknown action' }), {
    status: 400,
    headers: { 'Content-Type': 'application/json' }
  });
}
