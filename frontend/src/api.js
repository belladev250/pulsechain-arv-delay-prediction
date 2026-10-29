const KEY = "pulsechain_token";

export const getToken = () => window.localStorage.getItem(KEY);
export const setToken = (token) => window.localStorage.setItem(KEY, token);
export const clearToken = () => window.localStorage.removeItem(KEY);

export async function api(path, options = {}) {
  const token = getToken();
  const res = await fetch("/api" + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    let message = "Request failed";
    if (typeof err.detail === "string") {
      message = err.detail;
    } else if (Array.isArray(err.detail)) {
      message = err.detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
    }
    // An expired or rejected token signs the user out, except on the login call itself,
    // where a 401 just means a wrong password.
    if (res.status === 401 && token && !path.startsWith("/auth/login")) {
      clearToken();
      window.dispatchEvent(new Event("pulsechain-logout"));
    }
    throw new Error(message);
  }
  return res.json();
}
