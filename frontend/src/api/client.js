const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function toMessage(body, status) {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  // FastAPI validation errors arrive as a list of { loc, msg }.
  if (Array.isArray(detail)) return detail.map((entry) => entry.msg).join("; ");
  return `Request failed with status ${status}`;
}

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(toMessage(body, response.status));
  return body;
}

export const api = {
  listItems: () => request("/items"),
  ingest: (sourceType, content) =>
    request("/ingest", {
      method: "POST",
      body: JSON.stringify({ source_type: sourceType, content }),
    }),
  ask: (question, history = []) =>
    request("/query", {
      method: "POST",
      body: JSON.stringify({ question, history }),
    }),
};
