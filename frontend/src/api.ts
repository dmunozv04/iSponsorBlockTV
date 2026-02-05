// API client for iSponsorBlockTV

const API_BASE = "/api";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const credentials = localStorage.getItem("auth");

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (credentials) {
    headers["Authorization"] = `Basic ${credentials}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new ApiError(response.status, error.detail || "Request failed");
  }

  return response.json();
}

// Auth API
export const authApi = {
  checkStatus: () => request<{ configured: boolean }>("/auth/status"),

  setup: (username: string, password: string) =>
    request<{ message: string }>("/auth/setup", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  verify: () =>
    request<{ username: string; authenticated: boolean }>("/auth/verify"),

  changePassword: (oldPassword: string, newPassword: string) =>
    request<{ message: string }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({
        old_password: oldPassword,
        new_password: newPassword,
      }),
    }),
};

// Config API
export const configApi = {
  get: () => request<import("./types").Config>("/config"),

  update: (config: Partial<import("./types").Config>) =>
    request<{ message: string }>("/config", {
      method: "PUT",
      body: JSON.stringify(config),
    }),

  getCategories: () =>
    request<import("./types").Category[]>("/config/categories"),
};

// Device API
export const deviceApi = {
  list: () => request<import("./types").Device[]>("/devices"),

  add: (device: { screen_id: string; name: string; offset: number }) =>
    request<{ message: string; device: import("./types").Device }>("/devices", {
      method: "POST",
      body: JSON.stringify(device),
    }),

  remove: (screenId: string) =>
    request<{ message: string }>(`/devices/${encodeURIComponent(screenId)}`, {
      method: "DELETE",
    }),

  update: (
    screenId: string,
    device: { screen_id: string; name: string; offset: number },
  ) =>
    request<{ message: string }>(`/devices/${encodeURIComponent(screenId)}`, {
      method: "PUT",
      body: JSON.stringify(device),
    }),

  discover: () => request<import("./types").Device[]>("/devices/discover"),

  pair: (pairingCode: string) =>
    request<import("./types").Device>("/devices/pair", {
      method: "POST",
      body: JSON.stringify({ pairing_code: pairingCode }),
    }),
};

// Monitoring API
export const monitoringApi = {
  getStatus: () => request<import("./types").MonitoringStatus>("/status"),

  start: () => request<{ message: string }>("/start", { method: "POST" }),

  stop: () => request<{ message: string }>("/stop", { method: "POST" }),

  restart: () => request<{ message: string }>("/restart", { method: "POST" }),
};

// Channel API
export const channelApi = {
  search: (query: string) =>
    request<import("./types").ChannelSearchResult[]>(
      `/channels/search?q=${encodeURIComponent(query)}`,
    ),
};

export { ApiError };
