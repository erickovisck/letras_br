<div align="right">
  <a href="README.md"><img src="https://img.shields.io/badge/Language-English-blue?style=for-the-badge&logo=readme&logoColor=white" alt="English"></a>
  <a href="README.pt-BR.md"><img src="https://img.shields.io/badge/Língua-Português-green?style=for-the-badge&logo=readme&logoColor=white" alt="Português"></a>
</div>

# LetrasBR - Letras e Tradução Sincronizadas em Tempo Real

[![Versão](https://img.shields.io/badge/versão-3.0.0-blue.svg?style=flat-square)](https://github.com/erickovisck/letras_br)
[![Versão Python](https://img.shields.io/badge/python-3.10%2B-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-PySide6%20(Qt6)-41CD52.svg?style=flat-square&logo=qt&logoColor=white)](https://www.qt.io/)
[![Windows Media](https://img.shields.io/badge/Windows-GSMTC%20Nativo-0078D6.svg?style=flat-square&logo=windows&logoColor=white)](https://learn.microsoft.com)
[![Versão Android](https://img.shields.io/badge/android-API%2026%2B-3DDC84.svg?style=flat-square&logo=android&logoColor=white)](https://developer.android.com)
[![Licença: MIT](https://img.shields.io/badge/Licen%C3%A7a-MIT-green.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Download APK](https://img.shields.io/badge/Download%20APK-v2.1.0-brightgreen.svg?style=flat-square&logo=android)](https://github.com/erickovisck/letras_br/releases/latest)

> **Um ecossistema moderno e completo para sincronização e tradução de letras de música em tempo real. Agora 100% Desktop nativo no Windows com PySide6 (Qt 6) e integração direta com o Windows Media Controls (GSMTC) — detecta YouTube Music, Spotify e players de navegadores sem precisar de extensões!**

---

## Índice

- [Mudar Idioma](#-mudar-idioma)
- [Principais Recursos](#-principais-recursos)
- [Plataformas Suportadas](#-plataformas-suportadas)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Início Rápido Desktop (Windows)](#-início-rápido-desktop-windows)
  - [1. Executável LetrasBR.exe & Pesquisa no Windows](#1-executável-letrasbrexe--pesquisa-no-windows)
  - [2. Inicialização via Script (.bat)](#2-inicialização-via-script-bat)
  - [3. Como Funciona a Criação do Executável (.exe)](#3-como-funciona-a-criação-do-executável-exe)
- [Interface Visual & Personalização](#-interface-visual--personalização)
- [Aplicativo Android & Download do APK](#-aplicativo-android--download-do-apk)
- [Mobile Web & Picture-in-Picture (PiP)](#-mobile-web--picture-in-picture-pip)
- [Extensão Web (Legada / Opcional)](#-extensão-web-legada--opcional)
- [Solução de Problemas (FAQ)](#-solução-de-problemas-faq)
- [Licença & Autor](#-licença--autor)

---

## 🌐 Mudar Idioma

- 🇧🇷 **Português:** Versão atual
- 🇺🇸 **English:** [Click here to read the English version](README.md)

---

## ✨ Principais Recursos

- **100% Desktop Nativo (Windows GSMTC):** Monitora o YouTube Music (em qualquer navegador como Chrome, Edge, Brave, etc.), aplicativo de desktop do Spotify e outros players diretamente pelo sistema operacional Windows, sem depender de extensões.
- **Executável Nativo Integrado (`LetrasBR.exe`):** Inicializador Win32 silencioso (sem janela preta de console) com ícone embutido e registrado no Menu Iniciar do Windows — basta pressionar a tecla `Win` e digitar `LetrasBR`.
- **Animação 3D de Versos (Estilo Instagram Stories):** O verso anterior diminui e sobe em perspectiva 3D (indo para trás e para cima) enquanto o novo verso surge suavemente do fundo para o primeiro plano, renderizado em 60 FPS com `QPainter` nativo e sem artefatos de fundo opaco.
- **Miniplayer com Barra de Linha do Tempo (Seek Slider):** Controles ⏮, ⏯, ⏭ e barra de progresso interativa para avançar ou retroceder a música diretamente pelo overlay, com exibição de tempo em tempo real (`01:23 / 03:45`).
- **Alça de Redimensionamento Livre (`⇲`):** Localizada no canto inferior direito com cursor diagonal intuitivo para redimensionar largura e altura simultaneamente.
- **Menu de Configurações Completo (`⚙️`):**
  - Seletor de cor de fundo com controle deslizante de opacidade/transparência.
  - Seletores independentes de cor para a letra original e a tradução.
  - Seleção tipográfica completa de todas as fontes instaladas no Windows (`QFontComboBox`).
  - Ajuste de tamanho de fonte dividido e ergonômico: botões dedicados `[−]` e `[+]` e barra deslizante (10pt a 36pt).
  - Opções para Negrito e Itálico.
  - Modos de exibição flexíveis: Ambos, Apenas Tradução ou Apenas Original.
  - Configuração de URL para conexão a servidores remotos na rede local ou nuvem.
- **Resolução Inteligente de Autoplay & Troca Rápida de Música:** Feedback visual instantâneo (*"Carregando tradução..."*), cancelamento atômico de buscas antigas para evitar sobreposição de letras e limpeza avançada de metadados do YouTube (`(Official Video)`, `(Clip Oficial)`, `[Visualizer]`, etc.).
- **Bandeja do Sistema (System Tray):** Ícone ao lado do relógio do Windows com menu de contexto para ocultar/exibir overlay, controlar reprodução e encerrar a aplicação.
- **Tradução Multilíngue:** Suporte a Português (PT-BR), Inglês (EN), Espanhol (ES) e Francês (FR).

---

## 📱 Plataformas Suportadas

| Componente | Plataforma / Tecnologia | Descrição | Status |
| :--- | :--- | :--- | :---: |
| **App Desktop Principal** | Windows 10/11 (PySide6 / WinRT GSMTC) | Executável `LetrasBR.exe`, overlay translúcido, captura nativa | ✅ Disponível (v3.0) |
| **Servidor API Desacoplado** | Python 3.10+ / FastAPI | Backend local ou remoto de scraping e alinhamento de letras | ✅ Disponível |
| **App Nativo Android** | Android 8.0+ (Kotlin) | Leitor de mídia nativo + Janela flutuante (`SYSTEM_ALERT`) | ✅ APK Disponível |
| **Extensão Web (Opcional)** | Chromium (Chrome, Brave, Edge, Opera) | Content script MV3 para navegadores (mantida em `extension/`) | ✅ Legado/Opcional |

---

## 📁 Estrutura do Projeto

O projeto é organizado de forma modular e limpa:

```text
TRADUTOR YT MUSIC/
├── LetrasBR.exe              # Executável principal (raiz do projeto)
├── run_api.py                # Ponto de entrada do Python (GUI PySide6 + API FastAPI)
├── configurar_ambiente.bat   # Script de verificação e criação do .venv (Python >= 3.10)
├── iniciar_servidor.bat      # Script batch para inicialização rápida com console
│
├── assets/                   # Ícones e imagens do aplicativo
│   ├── app_icon.ico          # Ícone nativo do Windows (usado no .exe e na bandeja)
│   └── app_icon.png          # Ícone em alta resolução
│
├── config/                   # Arquivos de configuração do usuário
│   └── overlay_config.json   # Cores, fontes, opacidade, posição e tamanho da janela
│
├── scripts/                  # Utilitários de compilação e registro do Windows
│   ├── Launcher.cs           # Código-fonte em C# do inicializador Win32 silencioso
│   ├── build_exe.bat         # Compila o LetrasBR.exe usando o csc.exe nativo do .NET
│   ├── registrar_menu_iniciar.bat # Cria atalho no Menu Iniciar para pesquisa do Windows
│   └── registrar_protocolo.bat    # Registra o protocolo letrasbr:// no Registro
│
├── letrasbr_api/             # Módulos principais do backend e da interface gráfica
│   ├── overlay_qt.py         # Interface gráfica PySide6 (Janela flutuante, animação 3D, controles)
│   ├── media_monitor.py      # Monitor nativo de mídia do Windows (WinRT GSMTC)
│   ├── lyrics_client.py      # Cliente assíncrono de busca de letras com cancelamento de requests
│   ├── scraper.py            # Raspador de letras e traduções do letras.mus.br
│   ├── aligner.py            # Algoritmo de alinhamento temporal verso a verso
│   ├── config.py             # Gerenciador de leitura/gravação de configurações
│   ├── main.py               # Endpoints da API REST FastAPI
│   └── requirements.txt      # Dependências Python (PySide6, winrt, fastapi, etc.)
│
├── android/                  # Aplicativo Android nativo em Kotlin
└── extension/                # Extensão Web Chromium Manifest V3 (legada/opcional)
```

---

## 🚀 Início Rápido Desktop (Windows)

### Pré-requisitos
- **Windows 10 ou 11** (64 bits)
- **Python 3.10 ou superior** instalado no PATH ([Download Python](https://www.python.org/downloads/)).

### 1. Executável `LetrasBR.exe` & Pesquisa no Windows

O `LetrasBR.exe` está localizado na pasta principal do projeto.

1. **Configurar Ambiente pela Primeira Vez:**
   - Execute o script `configurar_ambiente.bat`. Ele verificará a versão do Python, criará a pasta `.venv`, instalará todas as dependências e registrará o atalho no Menu Iniciar.
2. **Abrir pelo Menu Iniciar:**
   - Pressione a tecla `Win` no teclado, digite **`LetrasBR`** e aperte **Enter**.
3. **Execução Direta:**
   - Dê um duplo clique em `LetrasBR.exe`. O aplicativo abrirá diretamente sem exibir janelas pretas de terminal.

### 2. Inicialização via Script (.bat)

Se preferir acompanhar as mensagens de log ou depuração no terminal:
- Dê um duplo clique em `iniciar_servidor.bat`.

---

### 3. Como Funciona a Criação do Executável (.exe)

O executável `LetrasBR.exe` foi desenvolvido para resolver o problema clássico de aplicações Python no Windows: a indesejada tela preta de prompt de comando (`cmd.exe`).

#### O Processo:
1. **Código-fonte em C# (`scripts/Launcher.cs`):**
   - É um programa Win32 compilado como `WinExe` (aplicativo gráfico sem console).
   - Ao ser clicado, ele detecta a pasta onde está rodando e localiza o interpretador silencioso do ambiente virtual: `.venv\Scripts\pythonw.exe`.
   - Se o `.venv` não existir, ele executa o `iniciar_servidor.bat` para auto-configurar.
   - O processo do Python é iniciado com as flags `CreateNoWindow = true` e `UseShellExecute = false`.
2. **Compilador Nativo do Windows (`csc.exe`):**
   - Não requer instalações pesadas como Visual Studio ou PyInstaller.
   - Utiliza o compilador nativo do Microsoft .NET Framework que já vem pré-instalado em todas as versões do Windows 10 e 11 em `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe`.
   - Embutiu o ícone do projeto (`assets/app_icon.ico`) diretamente no arquivo `.exe`.
3. **Recompilação:**
   - Para recompilar o `.exe` a qualquer momento após fazer alterações, basta executar:
     ```cmd
     scripts\build_exe.bat
     ```

---

## 🎨 Interface Visual & Personalização

O overlay flutuante pode ser completamente customizado para combinar com seu papel de parede ou tema de trabalho:

- **Arrastar e Posicionar:** Clique e arraste na barra superior escura para posicionar a janela onde preferir.
- **Redimensionar:** Clique e arraste o ícone `⇲` no canto inferior direito.
- **Avançar / Retroceder Música:** Use o slider de progresso localizado no topo ao lado dos botões de reprodução.
- **Menu de Configurações (`⚙️`):**
  - Ajuste a cor de fundo e a transparência em tempo real.
  - Altere a cor do verso original e da tradução.
  - Escolha qualquer fonte do sistema e ajuste o tamanho com precisão nos botões `[−]` e `[+]`.
  - Ative Negrito ou Itálico.
- **Bandeja do Sistema:** Clique com o botão direito no ícone do LetrasBR ao lado do relógio do Windows para atalhos rápidos ou para fechar.

---

## 📱 Aplicativo Android & Download do APK

O projeto inclui um app Android nativo desenvolvido em Kotlin que permite acompanhar as letras sincronizadas em uma bolha flutuante sobreposta ao YouTube Music no celular.

### 1. Baixar o APK

Baixe a versão mais recente em [Lançamentos (Releases)](https://github.com/erickovisck/letras_br/releases/latest):

[![Download APK](https://img.shields.io/badge/Download-APK%20Android%20(v2.1.0)-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://github.com/erickovisck/letras_br/releases/latest)

### 2. Permissões Necessárias:
1. Conceda permissão de **Acesso a Notificações / Sessão de Mídia**.
2. Conceda permissão para **Exibir sobre outros aplicativos**.
3. Aponte o IP do seu computador (exemplo: `http://192.168.1.15:8000`) e clique em **Testar Conexão**.

---

## 📱 Mobile Web & Picture-in-Picture (PiP)

Caso você utilize iOS ou não queira instalar o APK no Android:

1. Conecte o celular na mesma rede Wi-Fi do computador.
2. No navegador móvel, acesse:
   ```text
   http://<IP-DO-SEU-PC>:8000/mobile
   ```
3. Toque no botão **📺 PiP** para exibir as legendas sincronizadas em uma janela flutuante nativa do sistema móvel.

---

## 🧩 Extensão Web (Legada / Opcional)

A extensão Chromium (armazenada em `extension/`) continua disponível caso você prefira sincronizar a reprodução via injeção direta no navegador:
1. Abra `chrome://extensions` (ou `edge://extensions`, `brave://extensions`).
2. Ative o **Modo do Desenvolvedor**.
3. Clique em **Carregar sem compactação** e selecione a pasta `extension/`.

---

## ❓ Solução de Problemas (FAQ)

<details>
<summary><strong>1. O LetrasBR não detecta a música que está tocando</strong></summary>
Certifique-se de que o YouTube Music ou Spotify está sendo reproduzido no Windows. Verifique se o Windows Media Controls reconhece o player (ao apertar as teclas de volume do teclado, a janelinha com o título da música deve aparecer).
</details>

<details>
<summary><strong>2. O executável LetrasBR.exe não inicia</strong></summary>
Execute <code>configurar_ambiente.bat</code> uma vez para garantir que o ambiente <code>.venv</code> com Python >= 3.10 e as dependências do <code>requirements.txt</code> foram criadas com sucesso.
</details>

<details>
<summary><strong>3. O overlay não aparece sobre jogos em tela cheia</strong></summary>
Configure o jogo no modo <em>Janela Sem Bordas</em> (<em>Borderless Windowed</em>), pois o modo Tela Cheia Exclusivo do Windows impede a exibição de overlays flutuantes.
</details>

---

## 📄 Licença & Autor

Distribuído sob a licença **MIT**. Consulte `LICENSE` para mais detalhes.

**Autor:** [Erick Fernando Martins Santos](https://github.com/erickovisck)  
**GitHub:** [@erickovisck](https://github.com/erickovisck)  
**Email:** `erickmartinslima3@gmail.com`
