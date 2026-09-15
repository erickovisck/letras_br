// LetrasBR Mobile Overlay & PiP Controller
let apiUrl = localStorage.getItem("letrasbr_api_url") || window.location.origin;
if (apiUrl.endsWith("/")) apiUrl = apiUrl.slice(0, -1);

let config = {
  lang: localStorage.getItem("letrasbr_lang") || "pt",
  mode: localStorage.getItem("letrasbr_mode") || "both",
  fontSize: parseInt(localStorage.getItem("letrasbr_font") || "18"),
  opacity: parseInt(localStorage.getItem("letrasbr_opacity") || "90")
};

let currentState = {
  title: "",
  artist: "",
  orig: "",
  trans: "",
  isPaused: false,
  currTime: 0,
  durTime: 0,
  connected: false
};

// Elementos DOM
const elTitle = document.getElementById("song-title");
const elArtist = document.getElementById("song-artist");
const elOrig = document.getElementById("lyric-orig");
const elTrans = document.getElementById("lyric-trans");
const elStatusDot = document.getElementById("status-dot");
const elStatusText = document.getElementById("status-text");
const elTime = document.getElementById("time-display");
const elLangBadge = document.getElementById("current-lang-badge");
const elLyricsBox = document.querySelector(".lyrics-box");
const btnPlay = document.getElementById("btn-play");
const btnSkip = document.getElementById("btn-skip");
const btnPip = document.getElementById("btn-pip");

// Picture-in-Picture Elements
const pipCanvas = document.getElementById("pip-canvas");
const pipVideo = document.getElementById("pip-video");
const pipCtx = pipCanvas.getContext("2d");
let pipActive = false;

// ----------------------------------------------------
// Formatação de Tempo
// ----------------------------------------------------
function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// ----------------------------------------------------
// Comunicação com a API
// ----------------------------------------------------
async function fetchCurrentPlayback() {
  try {
    const res = await fetch(`${apiUrl}/api/current`, { method: "GET" });
    if (!res.ok) throw new Error("Status " + res.status);
    const data = await res.json();

    currentState.connected = true;
    currentState.title = data.title || "";
    currentState.artist = data.artist || "";
    currentState.orig = data.activeOriginal || "";
    currentState.trans = data.activeTranslation || "";
    currentState.isPaused = !!data.isPaused;
    currentState.currTime = data.currentSeconds || 0;
    currentState.durTime = data.durationSeconds || 0;
    if (data.lang) currentState.lang = data.lang;

    updateUI();
  } catch (err) {
    currentState.connected = false;
    updateUI();
  }
}

async function sendPlayerAction(action) {
  try {
    await fetch(`${apiUrl}/api/player/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: action })
    });
  } catch (err) {
    console.warn("Erro ao enviar ação:", err);
  }
}

async function changeLanguage(langCode) {
  config.lang = langCode;
  localStorage.setItem("letrasbr_lang", langCode);
  try {
    await fetch(`${apiUrl}/api/language`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lang: langCode })
    });
  } catch (err) {
    console.warn("Erro ao mudar idioma:", err);
  }
}

// ----------------------------------------------------
// Atualização de UI
// ----------------------------------------------------
function updateUI() {
  // Status de conexão
  if (currentState.connected) {
    elStatusDot.className = "dot connected";
    elStatusText.innerText = "Conectado à API";
  } else {
    elStatusDot.className = "dot disconnected";
    elStatusText.innerText = "Desconectado (Verifique a API)";
  }

  // Título e Artista
  if (currentState.title) {
    elTitle.innerText = currentState.title;
    elArtist.innerText = currentState.artist || "Desconhecido";
  } else {
    elTitle.innerText = "Nenhuma música tocando";
    elArtist.innerText = "Aguardando YouTube Music...";
  }

  // Letras
  if (!currentState.orig && !currentState.trans) {
    if (currentState.title) {
      elOrig.innerText = `${currentState.artist} - ${currentState.title}`;
      elTrans.innerText = "⏳ Aguardando início dos versos...";
    } else {
      elOrig.innerText = "Abra uma música no YouTube Music";
      elTrans.innerText = "";
    }
  } else {
    elOrig.innerText = currentState.orig || " ";
    elTrans.innerText = currentState.trans || " ";
  }

  // Modo de exibição
  if (config.mode === "trans") {
    elOrig.style.display = "none";
    elTrans.style.display = "block";
  } else if (config.mode === "orig") {
    elOrig.style.display = "block";
    elTrans.style.display = "none";
  } else {
    elOrig.style.display = "block";
    elTrans.style.display = "block";
  }

  // Miniplayer
  btnPlay.innerText = currentState.isPaused ? "▶" : "⏸";
  btnPlay.style.color = currentState.isPaused ? "#38bdf8" : "#ffffff";
  elTime.innerText = `${formatTime(currentState.currTime)} / ${formatTime(currentState.durTime)}`;
  elLangBadge.innerText = (currentState.lang || config.lang).toUpperCase();

  // Desenha no Canvas do PiP se ativo
  if (pipActive) {
    drawPiPCanvas();
  }
}

// ----------------------------------------------------
// Picture-in-Picture (PiP) com Canvas em Tempo Real
// ----------------------------------------------------
function drawPiPCanvas() {
  const w = pipCanvas.width;
  const h = pipCanvas.height;

  // Fundo escuro elegante
  pipCtx.fillStyle = "#0f1016";
  pipCtx.fillRect(0, 0, w, h);

  // Borda sutil
  pipCtx.strokeStyle = "#27273a";
  pipCtx.lineWidth = 4;
  pipCtx.strokeRect(2, 2, w - 4, h - 4);

  // Barra de título discreta no topo
  pipCtx.fillStyle = "#1e1e2d";
  pipCtx.fillRect(2, 2, w - 4, 34);

  pipCtx.fillStyle = "#94a3b8";
  pipCtx.font = "bold 14px sans-serif";
  pipCtx.textAlign = "left";
  pipCtx.fillText(`🎵 ${currentState.artist} - ${currentState.title}`, 14, 24);

  // Indicador de Idioma
  pipCtx.fillStyle = "#0284c7";
  pipCtx.fillRect(w - 55, 6, 45, 22);
  pipCtx.fillStyle = "#ffffff";
  pipCtx.font = "bold 11px sans-serif";
  pipCtx.textAlign = "center";
  pipCtx.fillText((currentState.lang || config.lang).toUpperCase(), w - 32, 21);

  // Desenha Verso Original
  const origText = currentState.orig || (currentState.title ? "Aguardando versos..." : "Aguardando música...");
  pipCtx.fillStyle = "#cbd5e1";
  pipCtx.font = "18px sans-serif";
  pipCtx.textAlign = "center";
  pipCtx.fillText(origText, w / 2, 105);

  // Desenha Verso Traduzido
  const transText = currentState.trans || "";
  pipCtx.fillStyle = "#38bdf8";
  pipCtx.font = "bold 22px sans-serif";
  pipCtx.textAlign = "center";
  pipCtx.fillText(transText, w / 2, 175);
}

async function startPiP() {
  try {
    drawPiPCanvas();

    if (!pipVideo.srcObject) {
      const stream = pipCanvas.captureStream(30);
      pipVideo.srcObject = stream;
      await pipVideo.play();
    }

    if (document.pictureInPictureElement) {
      await document.exitPictureInPicture();
    } else {
      await pipVideo.requestPictureInPicture();
      pipActive = true;
    }
  } catch (err) {
    alert("Não foi possível iniciar o Picture-in-Picture: " + err.message);
  }
}

pipVideo.addEventListener("leavepictureinpicture", () => {
  pipActive = false;
});

// ----------------------------------------------------
// Event Listeners
// ----------------------------------------------------
btnPlay.addEventListener("click", () => sendPlayerAction("play_pause"));
btnSkip.addEventListener("click", () => sendPlayerAction("next"));
btnPip.addEventListener("click", startPiP);

// Configurações
const modal = document.getElementById("settings-modal");
const btnSettings = document.getElementById("btn-settings");
const btnCloseModal = document.getElementById("btn-close-modal");
const btnSaveSettings = document.getElementById("btn-save-settings");
const sliderFont = document.getElementById("slider-font");
const fontVal = document.getElementById("font-val");
const sliderOpacity = document.getElementById("slider-opacity");
const opacityVal = document.getElementById("opacity-val");
const inputApiUrl = document.getElementById("api-url-input");

btnSettings.addEventListener("click", () => {
  inputApiUrl.value = localStorage.getItem("letrasbr_api_url") || "";
  sliderFont.value = config.fontSize;
  fontVal.innerText = `${config.fontSize}px`;
  sliderOpacity.value = config.opacity;
  opacityVal.innerText = `${config.opacity}%`;
  modal.classList.remove("hidden");
});

btnCloseModal.addEventListener("click", () => modal.classList.add("hidden"));
modal.addEventListener("click", (e) => {
  if (e.target === modal) modal.classList.add("hidden");
});

sliderFont.addEventListener("input", (e) => {
  const v = e.target.value;
  fontVal.innerText = `${v}px`;
  config.fontSize = parseInt(v);
  elOrig.style.fontSize = `${v}px`;
  elTrans.style.fontSize = `${Math.round(v * 1.15)}px`;
  localStorage.setItem("letrasbr_font", v);
});

sliderOpacity.addEventListener("input", (e) => {
  const v = e.target.value;
  opacityVal.innerText = `${v}%`;
  config.opacity = parseInt(v);
  elLyricsBox.style.opacity = v / 100;
  localStorage.setItem("letrasbr_opacity", v);
});

// Grupos de Idioma e Modo
document.querySelectorAll("#lang-group button").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#lang-group button").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    changeLanguage(btn.dataset.lang);
  });
});

document.querySelectorAll("#mode-group button").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#mode-group button").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    config.mode = btn.dataset.mode;
    localStorage.setItem("letrasbr_mode", config.mode);
    updateUI();
  });
});

btnSaveSettings.addEventListener("click", () => {
  const newUrl = inputApiUrl.value.trim();
  if (newUrl) {
    apiUrl = newUrl.endsWith("/") ? newUrl.slice(0, -1) : newUrl;
    localStorage.setItem("letrasbr_api_url", apiUrl);
  } else {
    apiUrl = window.location.origin;
    localStorage.removeItem("letrasbr_api_url");
  }
  modal.classList.add("hidden");
  fetchCurrentPlayback();
});

// Aplica configurações iniciais
elOrig.style.fontSize = `${config.fontSize}px`;
elTrans.style.fontSize = `${Math.round(config.fontSize * 1.15)}px`;
elLyricsBox.style.opacity = config.opacity / 100;

// Loop contínuo a cada 250ms
setInterval(fetchCurrentPlayback, 250);
fetchCurrentPlayback();
