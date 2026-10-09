const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const TOKEN_KEY = "token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

async function parseError(res) {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join(", ");
  } catch {
    // response was not JSON
  }
  return `Request failed (${res.status})`;
}

async function request(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let payload;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = new URLSearchParams(form).toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(`${API_URL}${path}`, { method, headers, body: payload });

  if (res.status === 401 && token && !path.startsWith("/auth/login")) {
    clearToken();
    window.location.href = "/";
    throw new Error("Session expired. Please log in again.");
  }
  if (!res.ok) throw new Error(await parseError(res));
  if (res.status === 204) return null;
  return res.json();
}

async function chatStream(body, onChunk) {
  const res = await fetch(`${API_URL}/ai/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onChunk(decoder.decode(value, { stream: true }));
  }
}

export const api = {
  register: (email, password) =>
    request("/auth/register", { method: "POST", body: { email, password } }),
  login: async (email, password) => {
    const data = await request("/auth/login", {
      method: "POST",
      form: { username: email, password },
    });
    setToken(data.access_token);
  },

  listProjects: () => request("/projects"),
  getProject: (id) => request(`/projects/${id}`),
  createProject: (name, description = "") =>
    request("/projects", { method: "POST", body: { name, description } }),
  deleteProject: (id) => request(`/projects/${id}`, { method: "DELETE" }),

  listFiles: (pid) => request(`/projects/${pid}/files`),
  createFile: (pid, data) => request(`/projects/${pid}/files`, { method: "POST", body: data }),
  updateFile: (pid, fid, data) =>
    request(`/projects/${pid}/files/${fid}`, { method: "PUT", body: data }),

  run: (code, language) => request("/code/run", { method: "POST", body: { code, language } }),
  runAndDebug: (code, language) =>
    request("/code/run-and-debug", { method: "POST", body: { code, language } }),

  explain: (code, language) =>
    request("/ai/explain", { method: "POST", body: { code, language } }),
  refactor: (code, language) =>
    request("/ai/refactor", { method: "POST", body: { code, language } }),

  history: (pid) => request(`/ai/history/${pid}`),
  chatStream,
};