# LetrasBR Tradutor - Aplicativo Android Nativo (Kotlin)

Aplicativo Android nativo em Kotlin que monitora o aplicativo oficial do **YouTube Music**, captura a música em tempo real e exibe a letra com tradução sincronizada em uma **janela flutuante (*floating overlay*)** sobre qualquer aplicativo.

---

## 📱 Recursos
- **Leitura Nativa do YouTube Music**: Usa `MediaSessionManager` e `NotificationListenerService` para capturar título, artista, duração e tempo exato de reprodução do app oficial do YouTube Music.
- **Janela Flutuante (*Always on Top*)**: Balão translúcido moderno arrastável por toque na tela.
- **Miniplayer Integrado**: Botões de **Play/Pause (`⏸`/`▶`)** e **Avançar (`⏭`)** diretamente na janela flutuante.
- **Suporte Multilíngue**: Tradução em Português (PT), Inglês (EN), Espanhol (ES) e Francês (FR).
- **Ultra Leve**: Menos de **3 MB** de tamanho total de APK compilado, com consumo mínimo de memória RAM e bateria.

---

## 🛠️ Como Compilar e Gerar o APK

### Opção 1: Via Android Studio (Recomendado)
1. Abra o **Android Studio**.
2. Clique em **File > Open** e selecione a pasta `android/` deste projeto.
3. Aguarde o Gradle sincronizar as dependências automaticamente.
4. No menu superior, clique em:
   `Build > Build Bundle(s) / APK(s) > Build APK(s)`.
5. O Android Studio gerará o APK na pasta:
   `android/app/build/outputs/apk/debug/app-debug.apk`.
6. Envie o arquivo `.apk` para o seu celular e instale!

### Opção 2: Pelo Terminal
Na pasta `android/`, execute:
```bash
./gradlew assembleDebug
```

---

## 🚀 Como Usar no Celular
1. Abra o app **LetrasBR Tradutor** instalado no celular.
2. Conceda as duas permissões necessárias:
   - **Leitura de Mídia / Notificações** (para detectar o YouTube Music).
   - **Janela Flutuante** (para exibir as letras sobrepostos a outros apps).
3. Digite o endereço IP do seu computador ou servidor na nuvem (ex: `http://192.168.1.15:8000`).
4. Toque em **Testar Conexão**.
5. Ative a chave **Ativar Balão Flutuante de Letras**.
6. Abra o aplicativo oficial do YouTube Music e dê play: a letra traduzida aparecerá flutuando na tela!
