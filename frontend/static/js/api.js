const API = (() => {
  const base = "";

  async function req(method, path, body) {
    const opts = { method, headers: {} };
    if (body instanceof FormData) {
      opts.body = body;
    } else if (body) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(base + path, opts);
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch {}
      throw new Error(detail);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  return {
    uploadFile: (formData) => req("POST", "/api/files/upload", formData),
    listFiles: () => req("GET", "/api/files"),
    getFile: (id) => req("GET", `/api/files/${id}`),
    deleteFile: (id) => req("DELETE", `/api/files/${id}`),

    getTileInfo: (fileId, channel, t, z) =>
      req("GET", `/api/tiles/${fileId}/info.json?channel=${channel}&t=${t}&z=${z}`),

    createJob: (body) => req("POST", "/api/jobs", body),
    getJob: (id) => req("GET", `/api/jobs/${id}`),
    getResults: (id) => req("GET", `/api/jobs/${id}/results`),
    getSegmenters: () => req("GET", "/api/segmenters"),
    health: () => req("GET", "/api/health"),
  };
})();
