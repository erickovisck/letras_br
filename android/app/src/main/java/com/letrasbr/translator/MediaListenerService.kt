package com.letrasbr.translator

import android.content.ComponentName
import android.content.Context
import android.media.MediaMetadata
import android.media.session.MediaController
import android.media.session.MediaSessionManager
import android.media.session.PlaybackState
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import kotlinx.coroutines.*

class MediaListenerService : NotificationListenerService() {

    private val serviceScope = CoroutineScope(Dispatchers.Default + Job())
    private var syncJob: Job? = null

    private var currentController: MediaController? = null
    private var lastTrackKey: String = ""

    companion object {
        var selectedLang: String = "pt"
        var isConnected: Boolean = false
            private set

        private var activeController: MediaController? = null

        fun togglePlayPause() {
            activeController?.let { controller ->
                val state = controller.playbackState?.state
                if (state == PlaybackState.STATE_PLAYING) {
                    controller.transportControls?.pause()
                } else {
                    controller.transportControls?.play()
                }
            }
        }

        fun skipNext() {
            activeController?.transportControls?.skipToNext()
        }
    }

    override fun onListenerConnected() {
        super.onListenerConnected()
        isConnected = true
        setupMediaSessionMonitoring()
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        isConnected = false
        stopSyncLoop()
        CoroutineScope(Dispatchers.IO).launch {
            ApiClient.clearPlayback()
        }
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        super.onNotificationPosted(sbn)
        // Re-escaneia sessões de mídia caso um novo player tenha iniciado
        refreshMediaControllers()
    }

    private fun setupMediaSessionMonitoring() {
        refreshMediaControllers()
        startSyncLoop()
    }

    private fun refreshMediaControllers() {
        try {
            val sessionManager = getSystemService(Context.MEDIA_SESSION_SERVICE) as MediaSessionManager
            val componentName = ComponentName(this, MediaListenerService::class.java)
            val controllers = sessionManager.getActiveSessions(componentName)

            // Prioriza players de música suportados (YouTube Music e Spotify)
            val playingApp = controllers.firstOrNull {
                it.playbackState?.state == PlaybackState.STATE_PLAYING &&
                        (it.packageName == "com.google.android.apps.youtube.music" || it.packageName == "com.spotify.music")
            }

            val musicApp = playingApp ?: controllers.firstOrNull {
                it.packageName == "com.google.android.apps.youtube.music" || it.packageName == "com.spotify.music"
            } ?: controllers.firstOrNull()

            val chosen = musicApp

            if (chosen != null && chosen.packageName != currentController?.packageName) {
                currentController = chosen
                activeController = chosen
                attachControllerCallbacks(chosen)
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun attachControllerCallbacks(controller: MediaController) {
        controller.registerCallback(object : MediaController.Callback() {
            override fun onMetadataChanged(metadata: MediaMetadata?) {
                super.onMetadataChanged(metadata)
            }

            override fun onPlaybackStateChanged(state: PlaybackState?) {
                super.onPlaybackStateChanged(state)
            }
        })
    }

    private fun startSyncLoop() {
        syncJob?.cancel()
        syncJob = serviceScope.launch {
            while (isActive) {
                try {
                    refreshMediaControllers()
                    val controller = currentController

                    if (controller != null) {
                        val metadata = controller.metadata
                        val playbackState = controller.playbackState

                        val title = metadata?.getString(MediaMetadata.METADATA_KEY_TITLE) ?: ""
                        val artist = metadata?.getString(MediaMetadata.METADATA_KEY_ARTIST) ?: ""
                        val durationMs = metadata?.getLong(MediaMetadata.METADATA_KEY_DURATION) ?: 0L

                        val positionMs = playbackState?.position ?: 0L
                        val isPaused = (playbackState?.state != PlaybackState.STATE_PLAYING)

                        if (title.isNotEmpty()) {
                            val isSpotify = controller.packageName == "com.spotify.music"
                            val source = if (isSpotify) "spotify" else "ytmusic"
                            val trackId = metadata?.getString(MediaMetadata.METADATA_KEY_MEDIA_ID)

                            val trackKey = "[$source] $artist - $title"
                            lastTrackKey = trackKey

                            val result = ApiClient.syncPlayback(
                                title = title,
                                artist = artist,
                                currentTimeSec = positionMs / 1000.0,
                                durationSec = durationMs / 1000.0,
                                isPaused = isPaused,
                                lang = selectedLang,
                                source = source,
                                trackId = trackId
                            )

                            if (result != null) {
                                // Atualiza a janela flutuante se estiver ativa
                                if (FloatingOverlayService.isRunning) {
                                    val prefix = if (isSpotify) "🟢 " else "🔴 "
                                    FloatingOverlayService.update(
                                        title = "$prefix$artist - $title",
                                        original = result.original,
                                        translation = result.translation,
                                        isPaused = isPaused
                                    )
                                }

                                // Trata comando se a API enviou
                                result.command?.let { cmd ->
                                    when (cmd) {
                                        "play_pause", "toggle_play" -> togglePlayPause()
                                        "next" -> skipNext()
                                    }
                                }
                            }
                        }
                    }
                } catch (e: Exception) {
                    // Trata silêncio de erros transitórios
                }
                delay(350)
            }
        }
    }

    private fun stopSyncLoop() {
        syncJob?.cancel()
    }

    override fun onDestroy() {
        super.onDestroy()
        stopSyncLoop()
        serviceScope.cancel()
        CoroutineScope(Dispatchers.IO).launch {
            ApiClient.clearPlayback()
        }
    }
}
