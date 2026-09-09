/**
 * fetch + JSON parse that never throws a bare "Unexpected token '<'".
 *
 * Calling res.json() before checking the response means any HTML reply — a Next.js
 * error or not-found page, a proxy 502 — surfaces as an opaque SyntaxError pointing
 * at a bundled chunk instead of at the request that actually failed. This checks the
 * content type first and reports the status and URL instead.
 *
 * In dev, a route handler that Turbopack has not compiled yet answers 404 with HTML
 * for the first moment after the server boots, so a 404/503 is retried once.
 */
export async function fetchJson<T = any>(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<T> {
  let res = await fetch(input, init);

  const isColdStart = res.status === 404 || res.status === 503;
  if (isColdStart && !isJsonResponse(res) && process.env.NODE_ENV !== 'production') {
    await new Promise((r) => setTimeout(r, 600));
    res = await fetch(input, init);
  }

  if (!isJsonResponse(res)) {
    const body = (await res.text()).trim().slice(0, 200);
    throw new Error(
      `${describe(input)} returned ${res.status} ${res.statusText} as ` +
        `${res.headers.get('content-type') || 'an unknown type'}, not JSON: ${body}`
    );
  }

  const json = await res.json();
  if (!res.ok) {
    throw new Error(json?.error || `${describe(input)} failed with ${res.status}`);
  }
  return json as T;
}

function isJsonResponse(res: Response) {
  return (res.headers.get('content-type') || '').includes('application/json');
}

function describe(input: RequestInfo | URL) {
  if (typeof input === 'string') return input;
  if (input instanceof URL) return input.toString();
  return input.url;
}
