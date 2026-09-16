// Content script do Spotify Web Tradutor LetrasBR
console.log("%c[LetrasBR Spotify]%c Script de sincronização iniciado no Spotify Web.", "color: #1db954; font-weight: bold;", "color: inherit;");

let lastSentSong = "";
let lastSentTime = -1;
let isConnected = false;
let currentLang = "pt";
let currentConfig = {
  opacity: 0.88,
  fontSize: 15,
  displayMode: "both",
  lang: "pt"
};

// Sincroniza configuração inicial com a API
function fetchInitialConfig() {
  chrome.runtime.sendMessage({ type: "LETRASBR_GET_CONFIG" }, (res) => {
    if (res && res.success && res.data) {
      currentConfig = Object.assign(currentConfig, res.data);
      if (currentConfig.lang) {
        currentLang = currentConfig.lang;
      }
    }
  });
}

function parseTimeToSeconds(timeStr) {
  if (!timeStr || typeof timeStr !== "string") return 0;
  const parts = timeStr.trim().split(":").map(p => parseFloat(p) || 0);
  if (parts.length === 2) {
    return parts[0] * 60 + parts[1];
  } else if (parts.length === 3) {
    return parts[0] * 3600 + parts[1] * 60 + parts[2];
  }
  return 0;
}

// Cria o badge de status e container de letras flutuante na interface do Spotify
function createStatusBadge() {
  if (document.getElementById("letrasbr-spotify-container")) return;

  const container = document.createElement("div");
  container.id = "letrasbr-spotify-container";
  container.style.position = "fixed";
  container.style.bottom = "100px";
  container.style.right = "24px";
  container.style.display = "flex";
  container.style.alignItems = "center";
  container.style.gap = "8px";
  container.style.zIndex = "999999";
  container.style.fontFamily = "Circular, Spotify Circular, Helvetica Neue, Helvetica, Arial, sans-serif";

  // Botão de Configurações ⚙️
  const btnSettings = document.createElement("button");
  btnSettings.id = "letrasbr-spotify-btn-settings";
  btnSettings.innerHTML = "⚙️";
  btnSettings.title = "Configurar Tradutor e Overlay";
  btnSettings.style.display = "flex";
  btnSettings.style.alignItems = "center";
  btnSettings.style.justifyContent = "center";
  btnSettings.style.width = "34px";
  btnSettings.style.height = "34px";
  btnSettings.style.borderRadius = "50%";
  btnSettings.style.backgroundColor = "rgba(18, 18, 18, 0.9)";
  btnSettings.style.border = "1px solid rgba(255, 255, 255, 0.25)";
  btnSettings.style.color = "#fff";
  btnSettings.style.fontSize = "16px";
  btnSettings.style.cursor = "pointer";
  btnSettings.style.backdropFilter = "blur(8px)";
  btnSettings.style.boxShadow = "0 4px 12px rgba(0,0,0,0.4)";
  btnSettings.style.transition = "transform 0.2s, background-color 0.2s";

  btnSettings.addEventListener("mouseenter", () => {
    btnSettings.style.transform = "scale(1.08)";
    btnSettings.style.backgroundColor = "rgba(40, 40, 40, 0.95)";
  });
  btnSettings.addEventListener("mouseleave", () => {
    btnSettings.style.transform = "scale(1.0)";
    btnSettings.style.backgroundColor = "rgba(18, 18, 18, 0.9)";
  });
  btnSettings.addEventListener("click", () => {
    openSettingsModal();
  });

  // Badge de status
  const badge = document.createElement("div");
  badge.id = "letrasbr-spotify-status-badge";
  badge.style.padding = "8px 14px";
  badge.style.borderRadius = "20px";
  badge.style.fontSize = "12px";
  badge.style.fontWeight = "600";
  badge.style.color = "#fff";
  badge.style.backgroundColor = "rgba(18, 18, 18, 0.9)";
  badge.style.backdropFilter = "blur(8px)";
  badge.style.border = "1px solid rgba(255, 255, 255, 0.18)";
  badge.style.boxShadow = "0 4px 15px rgba(0,0,0,0.4)";
  badge.style.cursor = "pointer";
  badge.style.transition = "all 0.3s ease";
  badge.innerText = "⏳ LetrasBR [Spotify]: Iniciando...";

  badge.addEventListener("click", () => {
    openSettingsModal();
  });

  // Botão de Iniciar API caso desconectado
  const btnStart = document.createElement("button");
  btnStart.id = "letrasbr-spotify-btn-start";
  btnStart.innerText = "▶ Iniciar Servidor";
  btnStart.title = "Iniciar a API local LetrasBR via protocolo";
  btnStart.style.padding = "7px 12px";
  btnStart.style.borderRadius = "20px";
  btnStart.style.fontSize = "12px";
  btnStart.style.fontWeight = "bold";
  btnStart.style.color = "#000";
  btnStart.style.backgroundColor = "#1db954";
  btnStart.style.border = "none";
  btnStart.style.boxShadow = "0 2px 10px rgba(29, 185, 84, 0.4)";
  btnStart.style.cursor = "pointer";
  btnStart.style.display = "none";
  btnStart.style.transition = "all 0.2s ease";

  btnStart.addEventListener("mouseenter", () => {
    btnStart.style.transform = "scale(1.05)";
    btnStart.style.backgroundColor = "#1ed760";
  });
  btnStart.addEventListener("mouseleave", () => {
    btnStart.style.transform = "scale(1.0)";
    btnStart.style.backgroundColor = "#1db954";
  });
  btnStart.addEventListener("click", () => {
    window.location.href = "letrasbr://start";
  });

  container.appendChild(btnSettings);
  container.appendChild(badge);
  container.appendChild(btnStart);
  document.body.appendChild(container);

  createLyricsOverlayBanner();
}

// Cria o banner horizontal de letras flutuante na tela do Spotify
function createLyricsOverlayBanner() {
  if (document.getElementById("letrasbr-spotify-lyrics-banner")) return;

  const banner = document.createElement("div");
  banner.id = "letrasbr-spotify-lyrics-banner";
  banner.style.position = "fixed";
  banner.style.bottom = "140px";
  banner.style.left = "50%";
  banner.style.transform = "translateX(-50%)";
  banner.style.backgroundColor = "rgba(15, 15, 20, 0.88)";
  banner.style.backdropFilter = "blur(12px)";
  banner.style.border = "1px solid rgba(255, 255, 255, 0.15)";
  banner.style.borderRadius = "14px";
  banner.style.padding = "10px 24px";
  banner.style.color = "#fff";
  banner.style.textAlign = "center";
  banner.style.zIndex = "999998";
  banner.style.maxWidth = "80vw";
  banner.style.boxShadow = "0 8px 30px rgba(0,0,0,0.5)";
  banner.style.transition = "all 0.2s ease";
  banner.style.display = "none";

  banner.innerHTML = `
    <div id="letrasbr-spot-orig" style="font-size: 13px; color: #a7a7a7; margin-bottom: 2px;"></div>
    <div id="letrasbr-spot-trans" style="font-size: 16px; font-weight: bold; color: #1db954;"></div>
  `;

  document.body.appendChild(banner);
}

function updateLyricsOverlay(original, translation) {
  const banner = document.getElementById("letrasbr-spotify-lyrics-banner");
  const origEl = document.getElementById("letrasbr-spot-orig");
  const transEl = document.getElementById("letrasbr-spot-trans");

  if (!banner || !origEl || !transEl) return;

  if (!original && !translation) {
    banner.style.display = "none";
    return;
  }

  banner.style.display = "block";
  origEl.innerText = original || "";
  transEl.innerText = translation || "";
}

function updateBadgeStatus(connected, songTitle = "", lang = "pt") {
  const badge = document.getElementById("letrasbr-spotify-status-badge");
  const btnStart = document.getElementById("letrasbr-spotify-btn-start");
  if (!badge) return;

  if (connected) {
    badge.style.backgroundColor = "rgba(20, 40, 25, 0.9)";
    badge.style.borderColor = "rgba(29, 185, 84, 0.4)";
    badge.innerText = `🟢 Spotify [${(lang || "PT").toUpperCase()}]: ${songTitle || "Sincronizado"}`;
    if (btnStart) btnStart.style.display = "none";
  } else {
    badge.style.backgroundColor = "rgba(45, 15, 15, 0.9)";
    badge.style.borderColor = "rgba(239, 68, 68, 0.4)";
    badge.innerText = "🔴 LetrasBR: Desconectado";
    if (btnStart) btnStart.style.display = "inline-block";
    updateLyricsOverlay("", "");
  }
}

// Modal de Configurações
function openSettingsModal() {
  let modal = document.getElementById("letrasbr-spotify-modal");
  if (modal) {
    modal.style.display = "flex";
    return;
  }

  modal = document.createElement("div");
  modal.id = "letrasbr-spotify-modal";
  modal.style.position = "fixed";
  modal.style.top = "0";
  modal.style.left = "0";
  modal.style.width = "100vw";
  modal.style.height = "100vh";
  modal.style.backgroundColor = "rgba(0,0,0,0.65)";
  modal.style.backdropFilter = "blur(6px)";
  modal.style.zIndex = "1000000";
  modal.style.display = "flex";
  modal.style.alignItems = "center";
  modal.style.justifyContent = "center";
  modal.style.fontFamily = "Circular, Spotify Circular, Helvetica Neue, sans-serif";

  modal.innerHTML = `
    <div style="background: #181818; border: 1px solid #333; border-radius: 16px; width: 380px; padding: 24px; color: #fff; box-shadow: 0 10px 40px rgba(0,0,0,0.7);">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h3 style="margin: 0; font-size: 18px; color: #1db954;">⚙️ LetrasBR Tradutor (Spotify)</h3>
        <button id="letrasbr-spot-modal-close" style="background: none; border: none; color: #999; font-size: 20px; cursor: pointer;">✕</button>
      </div>
      <p style="font-size: 12px; color: #b3b3b3; margin-bottom: 18px;">Configurações de sincronização e overlay de letras.</p>
      
      <div style="margin-bottom: 16px;">
        <label style="font-size: 13px; font-weight: bold; display: block; margin-bottom: 6px;">Idioma da Tradução:</label>
        <div style="display: flex; gap: 8px;">
          <button class="letrasbr-spot-lang-btn" data-lang="pt" style="flex: 1; padding: 8px; border-radius: 8px; border: 1px solid #444; background: #282828; color: #fff; cursor: pointer; font-weight: bold;">PT</button>
          <button class="letrasbr-spot-lang-btn" data-lang="en" style="flex: 1; padding: 8px; border-radius: 8px; border: 1px solid #444; background: #282828; color: #fff; cursor: pointer; font-weight: bold;">EN</button>
          <button class="letrasbr-spot-lang-btn" data-lang="es" style="flex: 1; padding: 8px; border-radius: 8px; border: 1px solid #444; background: #282828; color: #fff; cursor: pointer; font-weight: bold;">ES</button>
          <button class="letrasbr-spot-lang-btn" data-lang="fr" style="flex: 1; padding: 8px; border-radius: 8px; border: 1px solid #444; background: #282828; color: #fff; cursor: pointer; font-weight: bold;">FR</button>
        </div>
      </div>

      <div style="margin-top: 20px; display: flex; flex-direction: column; gap: 8px;">
        <button id="letrasbr-spot-btn-overlay" style="width: 100%; padding: 10px; border-radius: 10px; border: none; background: #1db954; color: #000; font-weight: bold; font-size: 13px; cursor: pointer;">
          🖥️ Abrir Overlay Flutuante do Windows
        </button>
        <button id="letrasbr-spot-btn-save" style="width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #444; background: #282828; color: #fff; font-size: 13px; cursor: pointer;">
          Fechar
        </button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  // Destaca idioma ativo
  const updateActiveLangButton = () => {
    modal.querySelectorAll(".letrasbr-spot-lang-btn").forEach(btn => {
      if (btn.getAttribute("data-lang") === currentLang) {
        btn.style.backgroundColor = "#1db954";
        btn.style.color = "#000";
        btn.style.borderColor = "#1db954";
      } else {
        btn.style.backgroundColor = "#282828";
        btn.style.color = "#fff";
        btn.style.borderColor = "#444";
      }
    });
  };
  updateActiveLangButton();

  // Cliques de idioma
  modal.querySelectorAll(".letrasbr-spot-lang-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const newLang = btn.getAttribute("data-lang");
      currentLang = newLang;
      updateActiveLangButton();
      chrome.runtime.sendMessage({
        type: "LETRASBR_SET_CONFIG",
        payload: { lang: newLang }
      });
    });
  });

  document.getElementById("letrasbr-spot-btn-overlay").addEventListener("click", () => {
    window.location.href = "letrasbr://start";
  });

  const closeModal = () => {
    modal.style.display = "none";
  };
  document.getElementById("letrasbr-spot-modal-close").addEventListener("click", closeModal);
  document.getElementById("letrasbr-spot-btn-save").addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });
}

// Executa comandos remotos no player do Spotify
function executePlayerCommand(command) {
  if (!command) return;
  console.log("[LetrasBR Spotify] Executando comando recebido:", command);

  switch (command) {
    case "play_pause":
    case "toggle_play": {
      const btn = document.querySelector('[data-testid="control-button-playpause"]');
      if (btn) btn.click();
      break;
    }
    case "next": {
      const btn = document.querySelector('[data-testid="control-button-skip-forward"]');
      if (btn) btn.click();
      break;
    }
    case "previous": {
      const btn = document.querySelector('[data-testid="control-button-skip-back"]');
      if (btn) btn.click();
      break;
    }
  }
}

// Extrai informações do player do Spotify Web
function extractSpotifyTrackInfo() {
  const titleEl = document.querySelector('[data-testid="context-item-info-title"] a') ||
                  document.querySelector('[data-testid="context-item-info-title"]');
  const artistEl = document.querySelector('[data-testid="context-item-info-subtitles"] a') ||
                   document.querySelector('[data-testid="context-item-info-subtitles"]') ||
                   document.querySelector('[data-testid="context-item-info-artist"]');
  const posEl = document.querySelector('[data-testid="playback-position"]');
  const durEl = document.querySelector('[data-testid="playback-duration"]');
  const playPauseBtn = document.querySelector('[data-testid="control-button-playpause"]');
  const linkEl = document.querySelector('a[data-testid="context-item-link"]') ||
                 document.querySelector('[data-testid="context-item-info-title"] a');

  if (!titleEl || !artistEl) return null;

  const title = (titleEl.innerText || "").trim();
  const artist = (artistEl.innerText || "").trim();
  if (!title || !artist) return null;

  const currentSec = parseTimeToSeconds(posEl ? posEl.innerText : "0:00");
  const durationSec = parseTimeToSeconds(durEl ? durEl.innerText : "0:00");

  let isPaused = false;
  if (playPauseBtn) {
    const aria = (playPauseBtn.getAttribute("aria-label") || "").toLowerCase();
    // Se o botão disser "Play" ou "Reproduzir" ou "Tocar", significa que está pausado
    if (aria.includes("play") || aria.includes("reproduzir") || aria.includes("tocar")) {
      isPaused = true;
    }
  }

  let trackId = null;
  if (linkEl && linkEl.href) {
    const match = linkEl.href.match(/track\/([a-zA-Z0-9]+)/);
    if (match) {
      trackId = `spotify:track:${match[1]}`;
    }
  }

  return {
    source: "spotify",
    title: title,
    artist: artist,
    trackId: trackId,
    currentTime: currentSec,
    duration: durationSec,
    isPaused: isPaused,
    lang: currentLang
  };
}

// Loop contínuo de sincronização (a cada 350ms)
function syncLoop() {
  const trackInfo = extractSpotifyTrackInfo();

  if (!trackInfo) {
    // Player ocioso
    setTimeout(syncLoop, 800);
    return;
  }

  chrome.runtime.sendMessage({
    type: "LETRASBR_SYNC",
    payload: trackInfo
  }, (res) => {
    if (chrome.runtime.lastError || !res || !res.success) {
      isConnected = false;
      updateBadgeStatus(false);
      setTimeout(syncLoop, 1500);
      return;
    }

    isConnected = true;
    const data = res.data;
    if (data && data.lang) {
      currentLang = data.lang;
    }

    updateBadgeStatus(true, `${trackInfo.artist} - ${trackInfo.title}`, currentLang);

    if (data && !trackInfo.isPaused) {
      updateLyricsOverlay(data.activeOriginal, data.activeTranslation);
    } else if (trackInfo.isPaused) {
      updateLyricsOverlay(data?.activeOriginal || "", "(Pausado)");
    }

    if (data && data.command) {
      executePlayerCommand(data.command);
    }

    setTimeout(syncLoop, 350);
  });
}

// Ao fechar a aba do Spotify, notifica o servidor para limpar a reprodução
window.addEventListener("beforeunload", () => {
  try {
    chrome.runtime.sendMessage({ type: "LETRASBR_CLEAR_PLAYBACK" });
  } catch (e) {}
});

// Inicialização
function init() {
  createStatusBadge();
  fetchInitialConfig();
  setTimeout(syncLoop, 1000);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
