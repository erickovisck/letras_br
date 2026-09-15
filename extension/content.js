// Content script do YouTube Music Tradutor LetrasBR
console.log("%c[LetrasBR]%c Script de sincronização iniciado no YouTube Music.", "color: #10b981; font-weight: bold;", "color: inherit;");

let lastSentSong = "";
let lastSentTime = -1;
let lastLogTime = 0;
let isConnected = false;
let currentLang = "pt";
let currentConfig = {
  opacity: 0.85,
  fontSize: 15,
  displayMode: "both",
  lang: "pt",
  x: 100,
  y: 100
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

// Cria o botão de configurações e badge de status na interface do YouTube Music
function createStatusBadge() {
  if (document.getElementById("letrasbr-container")) return;

  const container = document.createElement("div");
  container.id = "letrasbr-container";
  container.style.position = "fixed";
  container.style.bottom = "85px";
  container.style.right = "24px";
  container.style.display = "flex";
  container.style.alignItems = "center";
  container.style.gap = "8px";
  container.style.zIndex = "999999";
  container.style.fontFamily = "Segoe UI, Roboto, Helvetica, Arial, sans-serif";

  // Botão de Configuração ⚙️
  const btnSettings = document.createElement("button");
  btnSettings.id = "letrasbr-btn-settings";
  btnSettings.innerHTML = "⚙️";
  btnSettings.title = "Configurar Tradutor e Overlay Flutuante";
  btnSettings.style.display = "flex";
  btnSettings.style.alignItems = "center";
  btnSettings.style.justifyContent = "center";
  btnSettings.style.width = "34px";
  btnSettings.style.height = "34px";
  btnSettings.style.borderRadius = "50%";
  btnSettings.style.backgroundColor = "rgba(30, 30, 40, 0.9)";
  btnSettings.style.border = "1px solid rgba(255, 255, 255, 0.25)";
  btnSettings.style.color = "#fff";
  btnSettings.style.fontSize = "16px";
  btnSettings.style.cursor = "pointer";
  btnSettings.style.backdropFilter = "blur(8px)";
  btnSettings.style.boxShadow = "0 4px 12px rgba(0,0,0,0.3)";
  btnSettings.style.transition = "transform 0.2s, background-color 0.2s";

  btnSettings.addEventListener("mouseenter", () => {
    btnSettings.style.transform = "scale(1.08)";
    btnSettings.style.backgroundColor = "rgba(50, 50, 70, 0.95)";
  });
  btnSettings.addEventListener("mouseleave", () => {
    btnSettings.style.transform = "scale(1.0)";
    btnSettings.style.backgroundColor = "rgba(30, 30, 40, 0.9)";
  });
  btnSettings.addEventListener("click", () => {
    openSettingsModal();
  });

  // Badge de status
  const badge = document.createElement("div");
  badge.id = "letrasbr-status-badge";
  badge.style.padding = "8px 14px";
  badge.style.borderRadius = "20px";
  badge.style.fontSize = "12px";
  badge.style.fontWeight = "600";
  badge.style.color = "#fff";
  badge.style.backgroundColor = "rgba(20, 20, 28, 0.9)";
  badge.style.backdropFilter = "blur(8px)";
  badge.style.border = "1px solid rgba(255, 255, 255, 0.18)";
  badge.style.boxShadow = "0 4px 15px rgba(0,0,0,0.35)";
  badge.style.cursor = "pointer";
  badge.style.transition = "all 0.3s ease";
  badge.innerText = "⏳ LetrasBR: Iniciando...";

  badge.addEventListener("click", () => {
    openSettingsModal();
  });

  // Botão Iniciar API (visível quando a API estiver fechada)
  const btnStart = document.createElement("button");
  btnStart.id = "letrasbr-btn-start";
  btnStart.innerText = "▶ Iniciar API";
  btnStart.title = "Iniciar o servidor do Tradutor e abrir a janela flutuante";
  btnStart.style.padding = "7px 12px";
  btnStart.style.borderRadius = "18px";
  btnStart.style.fontSize = "11px";
  btnStart.style.fontWeight = "bold";
  btnStart.style.color = "#ffffff";
  btnStart.style.backgroundColor = "#10b981";
  btnStart.style.border = "none";
  btnStart.style.cursor = "pointer";
  btnStart.style.boxShadow = "0 4px 12px rgba(16, 185, 129, 0.4)";
  btnStart.style.display = "none";
  btnStart.style.alignItems = "center";
  btnStart.style.gap = "4px";
  btnStart.style.transition = "transform 0.2s, background-color 0.2s";

  btnStart.addEventListener("mouseenter", () => {
    btnStart.style.transform = "scale(1.06)";
    btnStart.style.backgroundColor = "#059669";
  });
  btnStart.addEventListener("mouseleave", () => {
    btnStart.style.transform = "scale(1.0)";
    btnStart.style.backgroundColor = "#10b981";
  });
  btnStart.addEventListener("click", () => {
    launchApi();
  });

  container.appendChild(btnSettings);
  container.appendChild(badge);
  container.appendChild(btnStart);
  document.body.appendChild(container);
}

function launchApi() {
  console.log("%c[LetrasBR]%c Iniciando servidor local via protocolo letrasbr://start...", "color: #10b981; font-weight: bold;", "color: inherit;");
  const a = document.createElement("a");
  a.href = "letrasbr://start";
  document.body.appendChild(a);
  a.click();
  setTimeout(() => a.remove(), 500);

  const btn = document.getElementById("letrasbr-btn-start");
  if (btn) {
    btn.innerText = "⏳ Abrindo...";
    btn.disabled = true;
    btn.style.opacity = "0.7";
    setTimeout(() => {
      if (btn) {
        btn.innerText = "▶ Iniciar API";
        btn.disabled = false;
        btn.style.opacity = "1";
      }
    }, 4000);
  }
}

function updateBadge(connected, text, tooltip = "") {
  const badge = document.getElementById("letrasbr-status-badge");
  const btnStart = document.getElementById("letrasbr-btn-start");
  if (!badge) return;
  badge.title = tooltip;
  if (connected) {
    badge.style.borderColor = "#10b981";
    badge.style.color = "#a7f3d0";
    badge.innerText = `🟢 LetrasBR [${currentLang.toUpperCase()}]: ${text}`;
    if (btnStart) btnStart.style.display = "none";
  } else {
    badge.style.borderColor = "#ef4444";
    badge.style.color = "#fca5a5";
    badge.innerText = `🔴 LetrasBR: ${text}`;
    if (btnStart) btnStart.style.display = "inline-flex";
  }
}

// Modal de Configurações
function openSettingsModal() {
  if (document.getElementById("letrasbr-modal-overlay")) return;

  // Busca dados mais recentes da API antes de renderizar
  chrome.runtime.sendMessage({ type: "LETRASBR_GET_CONFIG" }, (res) => {
    if (res && res.success && res.data) {
      currentConfig = Object.assign(currentConfig, res.data);
      if (currentConfig.lang) currentLang = currentConfig.lang;
    }
    renderModal();
  });
}

function renderModal() {
  const overlay = document.createElement("div");
  overlay.id = "letrasbr-modal-overlay";
  overlay.style.position = "fixed";
  overlay.style.top = "0";
  overlay.style.left = "0";
  overlay.style.width = "100vw";
  overlay.style.height = "100vh";
  overlay.style.backgroundColor = "rgba(0, 0, 0, 0.65)";
  overlay.style.backdropFilter = "blur(5px)";
  overlay.style.display = "flex";
  overlay.style.alignItems = "center";
  overlay.style.justifyContent = "center";
  overlay.style.zIndex = "1000000";
  overlay.style.fontFamily = "Segoe UI, Roboto, sans-serif";

  const modal = document.createElement("div");
  modal.id = "letrasbr-modal";
  modal.style.width = "420px";
  modal.style.maxWidth = "92vw";
  modal.style.backgroundColor = "#181824";
  modal.style.borderRadius = "16px";
  modal.style.border = "1px solid #2d3748";
  modal.style.boxShadow = "0 10px 30px rgba(0,0,0,0.6)";
  modal.style.color = "#f1f5f9";
  modal.style.padding = "22px 24px";
  modal.style.position = "relative";

  // Cabeçalho
  const header = document.createElement("div");
  header.style.display = "flex";
  header.style.alignItems = "center";
  header.style.justifyContent = "space-between";
  header.style.marginBottom = "18px";

  const title = document.createElement("h3");
  title.innerText = "⚙️ Configurações do Tradutor";
  title.style.margin = "0";
  title.style.fontSize = "16px";
  title.style.fontWeight = "bold";
  title.style.color = "#f8fafc";

  const btnClose = document.createElement("button");
  btnClose.innerHTML = "✕";
  btnClose.style.background = "none";
  btnClose.style.border = "none";
  btnClose.style.color = "#94a3b8";
  btnClose.style.fontSize = "16px";
  btnClose.style.cursor = "pointer";
  btnClose.addEventListener("click", () => overlay.remove());

  header.appendChild(title);
  header.appendChild(btnClose);
  modal.appendChild(header);

  // Aviso quando a API está desligada
  if (!isConnected) {
    const alertBanner = document.createElement("div");
    alertBanner.style.backgroundColor = "rgba(239, 68, 68, 0.12)";
    alertBanner.style.border = "1px solid rgba(239, 68, 68, 0.35)";
    alertBanner.style.borderRadius = "10px";
    alertBanner.style.padding = "10px 14px";
    alertBanner.style.marginBottom = "16px";
    alertBanner.style.display = "flex";
    alertBanner.style.alignItems = "center";
    alertBanner.style.justifyContent = "space-between";
    alertBanner.style.gap = "10px";

    const alertText = document.createElement("span");
    alertText.innerText = "⚠️ API do Tradutor está desligada.";
    alertText.style.fontSize = "12px";
    alertText.style.color = "#fca5a5";
    alertText.style.fontWeight = "600";

    const btnModalStart = document.createElement("button");
    btnModalStart.innerText = "▶ Iniciar API";
    btnModalStart.style.backgroundColor = "#10b981";
    btnModalStart.style.color = "#ffffff";
    btnModalStart.style.border = "none";
    btnModalStart.style.borderRadius = "8px";
    btnModalStart.style.padding = "6px 12px";
    btnModalStart.style.fontSize = "11px";
    btnModalStart.style.fontWeight = "bold";
    btnModalStart.style.cursor = "pointer";
    btnModalStart.style.boxShadow = "0 2px 8px rgba(16, 185, 129, 0.4)";
    btnModalStart.addEventListener("click", () => {
      launchApi();
      btnModalStart.innerText = "⏳ Abrindo...";
      btnModalStart.disabled = true;
    });

    alertBanner.appendChild(alertText);
    alertBanner.appendChild(btnModalStart);
    modal.appendChild(alertBanner);
  }

  // 1. Idioma
  const lblLang = document.createElement("label");
  lblLang.innerText = "Idioma da Tradução (Letras.mus.br):";
  lblLang.style.display = "block";
  lblLang.style.fontSize = "12px";
  lblLang.style.fontWeight = "600";
  lblLang.style.color = "#94a3b8";
  lblLang.style.marginBottom = "6px";
  modal.appendChild(lblLang);

  const langContainer = document.createElement("div");
  langContainer.style.display = "flex";
  langContainer.style.gap = "8px";
  langContainer.style.marginBottom = "16px";

  const langs = [
    { code: "pt", label: "🇧🇷 PT" },
    { code: "en", label: "🇺🇸 EN" },
    { code: "es", label: "🇪🇸 ES" },
    { code: "fr", label: "🇫🇷 FR" },
  ];

  langs.forEach(l => {
    const btn = document.createElement("button");
    btn.innerText = l.label;
    btn.dataset.code = l.code;
    btn.style.flex = "1";
    btn.style.padding = "7px 4px";
    btn.style.borderRadius = "8px";
    btn.style.border = "none";
    btn.style.cursor = "pointer";
    btn.style.fontSize = "12px";
    btn.style.fontWeight = "bold";

    const isSel = (l.code === currentLang);
    btn.style.backgroundColor = isSel ? "#0284c7" : "#27273a";
    btn.style.color = isSel ? "#fff" : "#94a3b8";

    btn.addEventListener("click", () => {
      currentLang = l.code;
      currentConfig.lang = l.code;
      lastSentSong = ""; // Força re-sincronização
      chrome.runtime.sendMessage({
        type: "LETRASBR_SET_CONFIG",
        payload: { lang: l.code }
      });
      langContainer.querySelectorAll("button").forEach(b => {
        const sel = b.dataset.code === l.code;
        b.style.backgroundColor = sel ? "#0284c7" : "#27273a";
        b.style.color = sel ? "#fff" : "#94a3b8";
      });
    });

    langContainer.appendChild(btn);
  });
  modal.appendChild(langContainer);

  // 2. Modo de Exibição
  const lblMode = document.createElement("label");
  lblMode.innerText = "Modo de Exibição no Overlay:";
  lblMode.style.display = "block";
  lblMode.style.fontSize = "12px";
  lblMode.style.fontWeight = "600";
  lblMode.style.color = "#94a3b8";
  lblMode.style.marginBottom = "6px";
  modal.appendChild(lblMode);

  const modeContainer = document.createElement("div");
  modeContainer.style.display = "flex";
  modeContainer.style.gap = "8px";
  modeContainer.style.marginBottom = "16px";

  const modes = [
    { code: "both", label: "Ambos" },
    { code: "trans", label: "Tradução" },
    { code: "orig", label: "Original" }
  ];

  modes.forEach(m => {
    const btn = document.createElement("button");
    btn.innerText = m.label;
    btn.dataset.code = m.code;
    btn.style.flex = "1";
    btn.style.padding = "7px 4px";
    btn.style.borderRadius = "8px";
    btn.style.border = "none";
    btn.style.cursor = "pointer";
    btn.style.fontSize = "12px";
    btn.style.fontWeight = "600";

    const isSel = (m.code === (currentConfig.displayMode || "both"));
    btn.style.backgroundColor = isSel ? "#0284c7" : "#27273a";
    btn.style.color = isSel ? "#fff" : "#94a3b8";

    btn.addEventListener("click", () => {
      currentConfig.displayMode = m.code;
      chrome.runtime.sendMessage({
        type: "LETRASBR_SET_CONFIG",
        payload: { displayMode: m.code }
      });
      modeContainer.querySelectorAll("button").forEach(b => {
        const sel = b.dataset.code === m.code;
        b.style.backgroundColor = sel ? "#0284c7" : "#27273a";
        b.style.color = sel ? "#fff" : "#94a3b8";
      });
    });

    modeContainer.appendChild(btn);
  });
  modal.appendChild(modeContainer);

  // 3. Opacidade do Overlay
  const opRow = document.createElement("div");
  opRow.style.display = "flex";
  opRow.style.justifyContent = "space-between";
  opRow.style.alignItems = "center";
  opRow.style.marginBottom = "4px";

  const lblOp = document.createElement("label");
  lblOp.innerText = "Opacidade:";
  lblOp.style.fontSize = "12px";
  lblOp.style.fontWeight = "600";
  lblOp.style.color = "#94a3b8";

  const valOp = document.createElement("span");
  valOp.innerText = `${Math.round((currentConfig.opacity || 0.85) * 100)}%`;
  valOp.style.fontSize = "12px";
  valOp.style.fontWeight = "bold";
  valOp.style.color = "#38bdf8";

  opRow.appendChild(lblOp);
  opRow.appendChild(valOp);
  modal.appendChild(opRow);

  const sliderOp = document.createElement("input");
  sliderOp.type = "range";
  sliderOp.min = "20";
  sliderOp.max = "100";
  sliderOp.value = Math.round((currentConfig.opacity || 0.85) * 100);
  sliderOp.style.width = "100%";
  sliderOp.style.marginBottom = "14px";
  sliderOp.style.accentColor = "#38bdf8";
  sliderOp.addEventListener("input", (e) => {
    const v = parseInt(e.target.value) / 100;
    valOp.innerText = `${e.target.value}%`;
    currentConfig.opacity = v;
    chrome.runtime.sendMessage({
      type: "LETRASBR_SET_CONFIG",
      payload: { opacity: v }
    });
  });
  modal.appendChild(sliderOp);

  // 4. Tamanho da Fonte
  const fsRow = document.createElement("div");
  fsRow.style.display = "flex";
  fsRow.style.justifyContent = "space-between";
  fsRow.style.alignItems = "center";
  fsRow.style.marginBottom = "4px";

  const lblFs = document.createElement("label");
  lblFs.innerText = "Tamanho da Fonte:";
  lblFs.style.fontSize = "12px";
  lblFs.style.fontWeight = "600";
  lblFs.style.color = "#94a3b8";

  const valFs = document.createElement("span");
  valFs.innerText = `${currentConfig.fontSize || 15} px`;
  valFs.style.fontSize = "12px";
  valFs.style.fontWeight = "bold";
  valFs.style.color = "#38bdf8";

  fsRow.appendChild(lblFs);
  fsRow.appendChild(valFs);
  modal.appendChild(fsRow);

  const sliderFs = document.createElement("input");
  sliderFs.type = "range";
  sliderFs.min = "11";
  sliderFs.max = "28";
  sliderFs.value = currentConfig.fontSize || 15;
  sliderFs.style.width = "100%";
  sliderFs.style.marginBottom = "14px";
  sliderFs.style.accentColor = "#38bdf8";
  sliderFs.addEventListener("input", (e) => {
    const v = parseInt(e.target.value);
    valFs.innerText = `${v} px`;
    currentConfig.fontSize = v;
    chrome.runtime.sendMessage({
      type: "LETRASBR_SET_CONFIG",
      payload: { fontSize: v }
    });
  });
  modal.appendChild(sliderFs);

  // 5. Tamanho da Janela (Largura e Altura)
  const lblSize = document.createElement("label");
  lblSize.innerText = "Tamanho da Janela Flutuante:";
  lblSize.style.display = "block";
  lblSize.style.fontSize = "12px";
  lblSize.style.fontWeight = "600";
  lblSize.style.color = "#94a3b8";
  lblSize.style.marginBottom = "6px";
  modal.appendChild(lblSize);

  const sizeBtnContainer = document.createElement("div");
  sizeBtnContainer.style.display = "flex";
  sizeBtnContainer.style.gap = "6px";
  sizeBtnContainer.style.marginBottom = "14px";

  const sizePresets = [
    { label: "Pequeno", w: 480, h: 95 },
    { label: "Padrão", w: 650, h: 115 },
    { label: "Grande", w: 820, h: 140 },
  ];

  sizePresets.forEach(p => {
    const btn = document.createElement("button");
    btn.innerText = `${p.label} (${p.w}x${p.h})`;
    btn.style.flex = "1";
    btn.style.padding = "6px 2px";
    btn.style.borderRadius = "8px";
    btn.style.border = "1px solid #3f3f5a";
    btn.style.backgroundColor = "#27273a";
    btn.style.color = "#cbd5e1";
    btn.style.fontSize = "11px";
    btn.style.fontWeight = "600";
    btn.style.cursor = "pointer";

    btn.addEventListener("click", () => {
      currentConfig.width = p.w;
      currentConfig.height = p.h;
      chrome.runtime.sendMessage({
        type: "LETRASBR_SET_CONFIG",
        payload: { width: p.w, height: p.h }
      });
    });
    sizeBtnContainer.appendChild(btn);
  });
  modal.appendChild(sizeBtnContainer);

  const tipResize = document.createElement("p");
  tipResize.innerText = "💡 Dica: Você também pode arrastar o ícone ⇲ no canto da janela para redimensionar livremente!";
  tipResize.style.fontSize = "11px";
  tipResize.style.color = "#64748b";
  tipResize.style.margin = "0 0 12px 0";
  modal.appendChild(tipResize);

  // Rodapé com Dica e Botão Resetar Posição
  const footer = document.createElement("div");
  footer.style.display = "flex";
  footer.style.alignItems = "center";
  footer.style.justifyContent = "space-between";
  footer.style.marginTop = "8px";

  const btnReset = document.createElement("button");
  btnReset.innerText = "📍 Centralizar Overlay";
  btnReset.style.padding = "8px 12px";
  btnReset.style.backgroundColor = "#27273a";
  btnReset.style.color = "#cbd5e1";
  btnReset.style.border = "1px solid #3f3f5a";
  btnReset.style.borderRadius = "8px";
  btnReset.style.fontSize = "11px";
  btnReset.style.fontWeight = "bold";
  btnReset.style.cursor = "pointer";
  btnReset.addEventListener("click", () => {
    chrome.runtime.sendMessage({
      type: "LETRASBR_SET_CONFIG",
      payload: { x: 200, y: 150 }
    });
  });

  const btnConfirm = document.createElement("button");
  btnConfirm.innerText = "Fechar";
  btnConfirm.style.padding = "8px 18px";
  btnConfirm.style.backgroundColor = "#38bdf8";
  btnConfirm.style.color = "#0f172a";
  btnConfirm.style.border = "none";
  btnConfirm.style.borderRadius = "8px";
  btnConfirm.style.fontSize = "12px";
  btnConfirm.style.fontWeight = "bold";
  btnConfirm.style.cursor = "pointer";
  btnConfirm.addEventListener("click", () => overlay.remove());

  footer.appendChild(btnReset);
  footer.appendChild(btnConfirm);
  modal.appendChild(footer);

  overlay.appendChild(modal);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.remove();
  });
  document.body.appendChild(overlay);
}

function getVideoId() {
  const urlParams = new URLSearchParams(window.location.search);
  let v = urlParams.get("v");
  if (v) return v;

  const link = document.querySelector("ytmusic-player-bar a[href*='watch?v=']");
  if (link && link.href) {
    try {
      const p = new URLSearchParams(new URL(link.href).search);
      if (p.get("v")) return p.get("v");
    } catch (e) {}
  }
  return null;
}

function getSongData() {
  const playerBar = document.querySelector("ytmusic-player-bar");
  const video = document.querySelector("video");

  if (!playerBar || !video) {
    return { error: "Player do YouTube Music ou elemento de vídeo não encontrado ainda." };
  }

  const titleEl = playerBar.querySelector(".title.ytmusic-player-bar") || playerBar.querySelector("yt-formatted-string.title");
  const title = titleEl ? titleEl.innerText.trim() : "";
  if (!title) {
    return { error: "Nenhuma música sendo reproduzida no momento." };
  }

  let artist = "";
  const byline = playerBar.querySelector(".byline.ytmusic-player-bar");
  if (byline) {
    const artistLink = byline.querySelector("a[href*='channel/'], a[href*='browse/']");
    if (artistLink) {
      artist = artistLink.innerText.trim();
    } else {
      const parts = byline.innerText.split("•");
      if (parts.length > 0) {
        artist = parts[0].trim();
      }
    }
  }

  const videoId = getVideoId();
  const currentTime = video.currentTime || 0;
  const duration = video.duration || 0;
  const isPaused = video.paused;

  return {
    title,
    artist: artist || "Desconhecido",
    videoId: videoId || "",
    currentTime,
    duration,
    isPaused,
    lang: currentLang
  };
}

function executePlayerCommand(cmd) {
  if (!cmd) return;
  console.log(`%c[LetrasBR]%c Executando comando do overlay: ${cmd.toUpperCase()}`, "color: #38bdf8; font-weight: bold;", "color: inherit;");
  if (cmd === "play_pause" || cmd === "toggle_play") {
    const playBtn = document.querySelector("#play-pause-button, .play-pause-button, ytmusic-player-bar #play-pause-button");
    if (playBtn) {
      playBtn.click();
    } else {
      const v = document.querySelector("video");
      if (v) {
        if (v.paused) v.play();
        else v.pause();
      }
    }
  } else if (cmd === "next") {
    const nextBtn = document.querySelector(".next-button, #next-button, ytmusic-player-bar .next-button, ytmusic-player-bar #next-button");
    if (nextBtn) {
      nextBtn.click();
    }
  }
}

function sendSync() {
  const data = getSongData();

  if (data.error) {
    updateBadge(false, "Aguardando Música", data.error);
    return;
  }

  const songKey = `${data.artist}-${data.title}-${data.videoId}-${data.lang}`;
  const timeDiff = Math.abs(data.currentTime - lastSentTime);

  // Envia a cada ~300ms ou se mudou de faixa ou play/pause
  if (songKey !== lastSentSong || timeDiff >= 0.25 || data.isPaused) {
    lastSentSong = songKey;
    lastSentTime = data.currentTime;

    chrome.runtime.sendMessage({ type: "LETRASBR_SYNC", payload: data }, (response) => {
      const now = Date.now();

      if (chrome.runtime.lastError || !response || !response.success) {
        isConnected = false;
        const errMsg = response?.error || chrome.runtime.lastError?.message || "Sem resposta do background";
        updateBadge(false, "API Desconectada", `Verifique se run_api.py está rodando na porta 8000. Erro: ${errMsg}`);

        if (now - lastLogTime > 5000) {
          console.warn("[LetrasBR] Falha na comunicação com a API local (http://localhost:8000/api/sync):", errMsg);
          lastLogTime = now;
        }
      } else {
        if (response.data && response.data.lang && response.data.lang !== currentLang) {
          currentLang = response.data.lang;
          currentConfig.lang = currentLang;
          console.log(`%c[LetrasBR]%c Idioma sincronizado com o servidor: ${currentLang.toUpperCase()}`, "color: #38bdf8; font-weight: bold;", "color: inherit;");
          // Atualiza botões no modal de configurações se estiver aberto
          document.querySelectorAll("#letrasbr-modal button[data-code]").forEach(b => {
            const sel = (b.dataset.code === currentLang);
            b.style.backgroundColor = sel ? "#0284c7" : "#27273a";
            b.style.color = sel ? "#fff" : "#94a3b8";
          });
        }
        if (response.data && response.data.command) {
          executePlayerCommand(response.data.command);
        }
        if (!isConnected) {
          isConnected = true;
          console.log(`%c[LetrasBR]%c Conectado à API local! Música: ${data.artist} - ${data.title}`, "color: #10b981; font-weight: bold;", "color: inherit;");
        }
        const stateStr = data.isPaused ? "⏸️ Pausado" : `${Math.floor(data.currentTime)}s`;
        updateBadge(true, `${data.title} (${stateStr})`, `Artista: ${data.artist} | VideoID: ${data.videoId}`);
      }
    });
  }
}

// Inicialização contínua
function init() {
  fetchInitialConfig();
  createStatusBadge();
  setInterval(sendSync, 350);
}

if (document.readyState === "complete" || document.readyState === "interactive") {
  init();
} else {
  window.addEventListener("load", init);
}
