<div align="right">
  <a href="README.md"><img src="https://img.shields.io/badge/Language-English-blue?style=for-the-badge&logo=readme&logoColor=white" alt="English"></a>
  <a href="README.pt-BR.md"><img src="https://img.shields.io/badge/Língua-Português-green?style=for-the-badge&logo=readme&logoColor=white" alt="Português"></a>
</div>

# LetrasBR - Letras e Tradução Sincronizadas em Tempo Real

[![Versão](https://img.shields.io/badge/versão-2.1.0-blue.svg?style=flat-square)](https://github.com/erickovisck/letras_br)
[![Versão Python](https://img.shields.io/badge/python-3.10%2B-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Versão Android](https://img.shields.io/badge/android-API%2026%2B-3DDC84.svg?style=flat-square&logo=android&logoColor=white)](https://developer.android.com)
[![Manifest da Extensão](https://img.shields.io/badge/extensão-Manifest%20V3-orange.svg?style=flat-square&logo=googlechrome&logoColor=white)](https://developer.chrome.com/docs/extensions/mv3/intro/)
[![Licença: MIT](https://img.shields.io/badge/Licen%C3%A7a-MIT-green.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Download APK](https://img.shields.io/badge/Download%20APK-v2.1.0-brightgreen.svg?style=flat-square&logo=android)](https://github.com/erickovisck/letras_br/releases/latest)

> **Um ecossistema moderno e ultra leve para sincronização e tradução de letras de música em tempo real no YouTube Music e Spotify Web. Inclui janela flutuante desktop personalizável (*always-on-top*), extensão para navegadores Chromium, modo Picture-in-Picture web e aplicativo nativo para Android.**

---

## Índice

- [Mudar Idioma](#-mudar-idioma)
- [Principais Recursos](#-principais-recursos)
- [Plataformas Suportadas & Ecossistema](#-plataformas-suportadas--ecossistema)
- [Arquitetura & Fluxo do Sistema](#-arquitetura--fluxo-do-sistema)
- [Guia de Instalação da Extensão](#-guia-de-instalação-da-extensão)
  - [1. Passo a Passo para Chrome, Brave e Edge](#1-passo-a-passo-para-chrome-brave-e-microsoft-edge)
  - [2. Verificação e Uso da Extensão](#2-verificação-e-uso-da-extensão)
- [Configuração do Servidor Desktop & Overlay](#-configuração-do-servidor-desktop--overlay)
  - [1. Pré-requisitos](#1-pré-requisitos)
  - [2. Início Rápido (Windows)](#2-início-rápido-windows)
  - [3. Instalação Manual & Opções via CLI](#3-instalação-manual--opções-via-cli)
- [Aplicativo Android & Download do APK](#-aplicativo-android--download-do-apk)
  - [1. Instalação do APK (Pronto para Uso)](#1-instalação-do-apk-pronto-para-uso)
  - [2. Permissões Necessárias no Celular](#2-permissões-necessárias-no-celular)
  - [3. Como Compilar pelo Código-Fonte](#3-como-compilar-pelo-código-fonte)
- [Overlay Mobile Web & Picture-in-Picture (PiP)](#-overlay-mobile-web--picture-in-picture-pip)
- [Configurações & Personalização](#-configurações--personalização)
- [Solução de Problemas (FAQ)](#-solução-de-problemas-faq)
- [Roadmap](#-roadmap)
- [Como Contribuir](#-como-contribuir)
- [Licença & Autor](#-licença--autor)

---

## 🌐 Mudar Idioma

- 🇧🇷 **Português:** Versão atual
- 🇺🇸 **English:** [Click here to read the English version](README.md)

---

## ✨ Principais Recursos

- **Sincronização Sub-segundo em Tempo Real:** Alinha milimetricamente as linhas de letra com o tempo de reprodução de áudio do YouTube Music e Spotify Web.
- **Tradução Multilíngue Instantânea:** Tradução linha a linha para Português (PT-BR), Inglês (EN), Espanhol (ES) e Francês (FR).
- **Overlay Flutuante Desktop (*Always-on-Top*):** Janela HUD transparente desenvolvida em Tkinter, reposicionável por clique e arraste, com ajuste dinâmico de opacidade, tamanho de fonte e esquemas de cores.
- **Extensão para Navegadores Chromium (Manifest V3):** Captura automaticamente metadados e carimbos de tempo das abas ativas sem exigir credenciais ou login.
- **Aplicativo Nativo Android (Kotlin):** Serviço em segundo plano com `MediaSessionManager` e `NotificationListenerService` exibindo letras flutuantes sobrepostas a qualquer aplicativo no celular.
- **Miniplayer Picture-in-Picture (PiP) Web:** Gerador de canvas de vídeo com legendas flutuantes nativas para dispositivos móveis ou navegadores.
- **Controles de Mídia Integrados:** Pause, play e avance faixas diretamente da janela flutuante desktop ou mobile.
- **Protocolo de Inicialização em 1 Clique:** Protocolo personalizado do Windows (`letrasbr://`) permitindo inicializar o servidor e overlay diretamente por botões do navegador.

---

## 📱 Plataformas Suportadas & Ecossistema

| Componente | Plataforma / Tecnologia | Descrição | Status |
| :--- | :--- | :--- | :---: |
| **Extensão Web** | Navegadores Chromium (Chrome, Brave, Edge, Opera) | Content script MV3 monitorando YouTube Music & Spotify | ✅ Disponível |
| **Servidor Desktop & Overlay** | Python 3.10+ / FastAPI / Tkinter | API local em `localhost:8000` + HUD flutuante | ✅ Disponível |
| **App Nativo Android** | Android 8.0+ (Kotlin) | Leitor de mídia nativo + Janela flutuante (`SYSTEM_ALERT`) | ✅ APK Disponível |
| **Overlay Mobile Web** | HTML5 Canvas / Vídeo PiP | Interface web responsiva com Picture-in-Picture | ✅ Disponível |

---

## 🏗 Arquitetura & Fluxo do Sistema

```text
  +-------------------------------------------------------------+
  |                  Fonte de Áudio no Navegador                |
  |             (music.youtube.com / open.spotify.com)          |
  +-------------------------------------------------------------+
                                 |
                                 | (Tempo de reprodução DOM & metadados)
                                 v
  +-------------------------------------------------------------+
  |             Extensão LetrasBR para Navegador (MV3)          |
  |     - content.js / spotify_content.js                       |
  |     - background.js (proxy & heartbeat de conexão)          |
  +-------------------------------------------------------------+
                                 |
                                 | HTTP POST /sync (title, artist, position, is_paused)
                                 v
  +-------------------------------------------------------------+
  |              API Local Python LetrasBR (FastAPI)            |
  |                     (http://localhost:8000)                 |
  +-------------------------------------------------------------+
            |                                       |
            | (Busca & Alinha Letras/Traduções)     | (Transmite estado de reprodução)
            v                                       v
  +--------------------+         +--------------------------------------+
  | Scraper & Provedores|        | Overlay Flutuante Desktop (Tkinter)  |
  | - Letras.mus.br    |         | - Janela transparente arrastável     |
  | - YtMusicApi Sync  |         | - Botões de Mídia (Play/Pause/Skip)  |
  +--------------------+         +--------------------------------------+
                                                    ^
                                                    | (Polling / Sincronização HTTP)
                                 +--------------------------------------+
                                 | App Nativo Android / Mobile Web PiP  |
                                 | - Janela Flutuante (SYSTEM_ALERT)    |
                                 +--------------------------------------+
```

---

## 📦 Guia de Instalação da Extensão

A extensão conecta o reprodutor web do YouTube Music ou Spotify ao servidor local de alinhamento de letras.

### 1. Passo a Passo para Chrome, Brave e Microsoft Edge

1. **Baixe ou Clone este Repositório:**
   ```bash
   git clone https://github.com/erickovisck/letras_br.git
   ```
   *(Ou baixe o arquivo ZIP pelo GitHub e extraia os arquivos no seu computador).*

2. **Abra a Página de Extensões do Navegador:**
   - **Google Chrome:** Digite `chrome://extensions` na barra de endereços e pressione Enter.
   - **Brave Browser:** Digite `brave://extensions` na barra de endereços e pressione Enter.
   - **Microsoft Edge:** Digite `edge://extensions` na barra de endereços e pressione Enter.
   - **Opera / Opera GX:** Digite `opera://extensions` na barra de endereços e pressione Enter.

3. **Ative o Modo do Desenvolvedor:**
   - No canto superior direito da tela de extensões, ative a chave **"Modo do desenvolvedor"** (*Developer mode*).

4. **Carregar Extensão sem Compactação:**
   - Clique no botão **"Carregar sem compactação"** (*Load unpacked*) que aparecerá no canto superior esquerdo.
   - Na janela de seleção de pastas, navegue até o repositório clonado e selecione a pasta **`extension`**:
     ```text
     letras_br/
     ├── android/
     ├── extension/   <--- SELECIONE ESTA PASTA
     │   ├── manifest.json
     │   ├── background.js
     │   ├── content.js
     │   └── spotify_content.js
     ├── letrasbr_api/
     ...
     ```

5. **Confirmação:**
   - O card da extensão **LetrasBR Tradutor - YouTube Music & Spotify** aparecerá listado e ativo na versão `2.0.0+`.

---

### 2. Verificação e Uso da Extensão

1. Verifique se o servidor desktop está iniciado (veja [Configuração do Servidor Desktop](#-configuração-do-servidor-desktop--overlay)).
2. Acesse o [YouTube Music](https://music.youtube.com) ou o [Spotify Web](https://open.spotify.com).
3. No canto inferior direito da tela, você verá o botão flutuante de status com o ícone de engrenagem `⚙️`.
4. Dê play em qualquer música: o título e a minutagem serão sincronizados instantaneamente!

---

## 🖥️ Configuração do Servidor Desktop & Overlay

O servidor local é o motor que busca as letras, calcula o alinhamento com a tradução e renderiza a janela flutuante no Windows.

### 1. Pré-requisitos & Dependências

- Python 3.10 ou superior instalado com suporte ao Tkinter:
  ```bash
  python --version
  ```
- **[ytmusicapi](https://github.com/sigma67/ytmusicapi)** ([PyPI](https://pypi.org/project/ytmusicapi/)): Biblioteca cliente oficial utilizada pelo backend para consultar os endpoints internos do YouTube Music e extrair as letras temporizadas (*timestamped lyrics*).

### 2. Início Rápido (Windows)

Você possui dois scripts prontos na raiz do projeto:

- **`configurar_ambiente.bat`**: Executa a configuração inicial completa (valida o Python, cria o `.venv`, instala o `requirements.txt` e registra o protocolo no Windows).
- **`iniciar_servidor.bat`**: Inicia o servidor e o overlay. **Auto-configurável:** Se o ambiente virtual ou as dependências ainda não tiverem sido carregados, ele executa essa configuração automaticamente antes de iniciar!

```cmd
# Basta dar um duplo clique:
iniciar_servidor.bat
```

### 3. Instalação Manual & Opções via CLI

```bash
# 1. Crie e ative um ambiente virtual
python -m venv .venv
.venv\Scripts\activate       # No Windows
# source .venv/bin/activate  # No Linux/macOS

# 2. Instale as dependências (incluindo o ytmusicapi)
pip install -r letrasbr_api/requirements.txt

# Ou se preferir instalar a biblioteca ytmusicapi individualmente:
# pip install ytmusicapi

# 3. Registre o protocolo do Windows para inicialização em 1 clique (opcional)
python letrasbr_api/protocol.py

# 4. Inicie o servidor com o overlay gráfico
python run_api.py
```

#### Modo Sem Interface (Apenas Servidor)
Caso queira rodar apenas a API para servir o aplicativo Android na sua rede local sem abrir a janela no computador:

```bash
python run_api.py --no-overlay
```

---

## 📱 Aplicativo Android & Download do APK

Um aplicativo Android nativo desenvolvido em Kotlin permite acompanhar as letras com tradução em uma janela flutuante sobreposta ao app oficial do YouTube Music no celular.

### 1. Instalação do APK (Pronto para Uso)

Você pode baixar diretamente a versão compilada mais recente do APK em lançamentos (*Releases*):

[![Download APK](https://img.shields.io/badge/Download-APK%20Android%20(v2.1.0)-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://github.com/erickovisck/letras_br/releases/latest)

> 💡 *Dica: Se estiver baixando o arquivo diretamente no celular, autorize a opção "Instalar aplicativos de fontes desconhecidas" no seu navegador ou gerenciador de arquivos.*

### 2. Permissões Necessárias no Celular

Ao abrir o aplicativo pela primeira vez:
1. Abra o app **LetrasBR Tradutor**.
2. Conceda permissão de **Acesso a Notificações / Sessão de Mídia** (para capturar qual música está tocando no YouTube Music).
3. Conceda permissão para **Exibir sobre outros aplicativos** (para desenhar o balão flutuante na tela).
4. Informe o endereço IP local do seu computador rodando a API (exemplo: `http://192.168.1.15:8000`).
5. Toque em **Testar Conexão**, ative a chave **Ativar Balão Flutuante de Letras** e aproveite!

### 3. Como Compilar pelo Código-Fonte

Caso prefira compilar o projeto Android você mesmo:

```bash
cd android
./gradlew assembleDebug
```
O APK final será gerado no caminho:
`android/app/build/outputs/apk/debug/app-debug.apk`.

---

## 📱 Overlay Mobile Web & Picture-in-Picture (PiP)

Caso você utilize iOS ou não queira instalar o APK no Android:

1. Conecte o celular na mesma rede Wi-Fi do computador.
2. Abra o navegador móvel e acesse:
   ```text
   http://<IP-DO-SEU-PC>:8000/mobile
   ```
3. Toque no botão **📺 PiP** para iniciar a janela flutuante nativa com legendas sincronizadas sobre qualquer tela!

---

## ⚙️ Configurações & Personalização

As preferências podem ser ajustadas em tempo real tanto no ícone de engrenagem `⚙️` do overlay desktop quanto pela interface da extensão:

- **Idiomas disponíveis:** Português (`pt`), Inglês (`en`), Espanhol (`es`) e Francês (`fr`).
- **Modos de Exibição:**
  - `both`: Letra original + Linha traduzida.
  - `translation`: Apenas linha traduzida.
  - `original`: Apenas linha original.
- **Aparência:** Controle de opacidade da janela, redimensionamento de fonte e paleta de cores.

---

## ❓ Solução de Problemas (FAQ)

<details>
<summary><strong>1. A extensão indica status "Offline" ou não se conecta</strong></summary>
Certifique-se de que o servidor Python está rodando através do comando <code>python run_api.py</code> ou pelo atalho <code>iniciar_servidor.bat</code>. Teste abrindo <a href="http://localhost:8000/">http://localhost:8000/</a> no navegador.
</details>

<details>
<summary><strong>2. O overlay desktop não aparece em cima de jogos ou vídeos em tela cheia</strong></summary>
Certifique-se de configurar o jogo ou player em <em>Modo Janela Sem Bordas</em> (<em>Borderless Windowed</em>), pois o modo Tela Cheia Exclusivo do Windows bloqueia janelas sobrepostas de terceiros.
</details>

<details>
<summary><strong>3. O app Android não consegue se conectar à API</strong></summary>
Verifique se o smartphone e o computador estão exatamente na mesma rede Wi-Fi. Certifique-se de que o Firewall do Windows não está bloqueando conexões de entrada na porta <code>8000</code>.
</details>

---

## 🗺 Roadmap

- [ ] Lançamento oficial na Chrome Web Store.
- [ ] Suporte ao reprodutor web do Apple Music.
- [ ] Cache local de letras em banco de dados SQLite.
- [ ] Efeito karaokê com destaque palavra por palavra.

---

## 🤝 Como Contribuir

Contribuições, correções de bugs e novas ideias são muito bem-vindas!

1. Faça um Fork do repositório.
2. Crie uma branch para sua funcionalidade (`git checkout -b feature/minha-feature`).
3. Faça commit das alterações com mensagens em português (`git commit -m 'feat: suporte a novas fontes de letras'`).
4. Envie o push para a sua branch (`git push origin feature/minha-feature`).
5. Abra um Pull Request detalhando as melhorias.

---

## 📄 Licença & Autor

Distribuído sob a licença **MIT**. Consulte `LICENSE` para mais informações.

**Autor:** [Erick Fernando Martins Santos](https://github.com/erickovisck)  
**GitHub:** [@erickovisck](https://github.com/erickovisck)  
**Email:** `erickmartinslima3@gmail.com`
