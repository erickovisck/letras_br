// Service worker de fundo para contornar Mixed Content e CSP do YouTube Music
console.log("[LetrasBR Background] Service Worker iniciado.");

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "LETRASBR_SYNC") {
    const data = message.payload;
    fetch("http://localhost:8000/api/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`Status ${res.status}: ${res.statusText}`);
        const json = await res.json();
        sendResponse({ success: true, data: json });
      })
      .catch((err) => {
        sendResponse({ success: false, error: err.message });
      });
    return true;
  }

  if (message.type === "LETRASBR_GET_CONFIG") {
    fetch("http://localhost:8000/api/config")
      .then(async (res) => {
        if (!res.ok) throw new Error(`Status ${res.status}`);
        const json = await res.json();
        sendResponse({ success: true, data: json });
      })
      .catch((err) => {
        sendResponse({ success: false, error: err.message });
      });
    return true;
  }

  if (message.type === "LETRASBR_SET_CONFIG") {
    fetch("http://localhost:8000/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(message.payload || {})
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`Status ${res.status}`);
        const json = await res.json();
        sendResponse({ success: true, data: json });
      })
      .catch((err) => {
        sendResponse({ success: false, error: err.message });
      });
    return true;
  }
});
