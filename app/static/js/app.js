window.ATBIS_BASE = window.ATBIS_BASE || "/atbis";

function showAlert(containerId, message, type = "info") {
  const container = document.getElementById(containerId);
  if (!container) {
    return;
  }
  container.innerHTML = `<div class="alert alert-${type}" role="alert">${message}</div>`;
}

async function apiFetch(path, options = {}) {
  const config = {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    credentials: "same-origin",
    ...options,
  };

  try {
    const response = await fetch(`${window.ATBIS_BASE}${path}`, config);
    const data = await response.json();
    if (!response.ok) {
      return {
        success: false,
        message: data.message || `HTTP ${response.status}`,
      };
    }
    return data;
  } catch (err) {
    return { success: false, message: err.message || "連線失敗" };
  }
}
