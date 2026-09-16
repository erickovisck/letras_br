package com.letrasbr.translator

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.TextView
import androidx.core.app.NotificationCompat

class FloatingOverlayService : Service() {

    private var windowManager: WindowManager? = null
    private var overlayView: View? = null
    private var layoutParams: WindowManager.LayoutParams? = null

    companion object {
        var isRunning: Boolean = false
            private set

        private var instance: FloatingOverlayService? = null

        fun update(title: String, original: String, translation: String, isPaused: Boolean) {
            instance?.updateUI(title, original, translation, isPaused)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        instance = this
        isRunning = true

        startForegroundServiceNotification()
        createFloatingOverlay()
    }

    private fun startForegroundServiceNotification() {
        val channelId = "letrasbr_overlay_channel"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                getString(R.string.channel_name),
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = getString(R.string.channel_desc)
            }
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }

        val notification: Notification = NotificationCompat.Builder(this, channelId)
            .setContentTitle("Tradutor LetrasBR")
            .setContentText("Balão flutuante ativo na tela")
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()

        startForeground(1001, notification)
    }

    private fun createFloatingOverlay() {
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager

        val layoutType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        }

        layoutParams = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            layoutType,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or
                    WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = 30
            y = 150
            width = (resources.displayMetrics.widthPixels * 0.92).toInt()
        }

        val inflater = LayoutInflater.from(this)
        overlayView = inflater.inflate(R.layout.overlay_layout, null)

        setupOverlayInteractions(overlayView!!)

        try {
            windowManager?.addView(overlayView, layoutParams)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun setupOverlayInteractions(view: View) {
        val header = view.findViewById<View>(R.id.overlay_header)
        val btnPlay = view.findViewById<TextView>(R.id.overlay_btn_play)
        val btnNext = view.findViewById<TextView>(R.id.overlay_btn_next)
        val btnClose = view.findViewById<TextView>(R.id.overlay_btn_close)

        // Arraste por toque
        var initialX = 0
        var initialY = 0
        var initialTouchX = 0f
        var initialTouchY = 0f

        val touchListener = View.OnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    initialX = layoutParams?.x ?: 0
                    initialY = layoutParams?.y ?: 0
                    initialTouchX = event.rawX
                    initialTouchY = event.rawY
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    layoutParams?.x = initialX + (event.rawX - initialTouchX).toInt()
                    layoutParams?.y = initialY + (event.rawY - initialTouchY).toInt()
                    windowManager?.updateViewLayout(overlayView, layoutParams)
                    true
                }
                else -> false
            }
        }

        header.setOnTouchListener(touchListener)
        view.findViewById<View>(R.id.overlay_root).setOnTouchListener(touchListener)

        // Miniplayer: Play/Pause
        btnPlay.setOnClickListener {
            MediaListenerService.togglePlayPause()
        }

        // Miniplayer: Próxima
        btnNext.setOnClickListener {
            MediaListenerService.skipNext()
        }

        // Fechar Overlay
        btnClose.setOnClickListener {
            stopSelf()
        }
    }

    fun updateUI(title: String, original: String, translation: String, isPaused: Boolean) {
        overlayView?.let { v ->
            v.post {
                val tvTitle = v.findViewById<TextView>(R.id.overlay_title)
                val tvOrig = v.findViewById<TextView>(R.id.overlay_text_original)
                val tvTrans = v.findViewById<TextView>(R.id.overlay_text_translation)
                val btnPlay = v.findViewById<TextView>(R.id.overlay_btn_play)

                if (title.isNotEmpty()) {
                    tvTitle.text = title
                }

                tvOrig.text = original.ifEmpty { "Aguardando versos..." }
                tvTrans.text = translation

                btnPlay.text = if (isPaused) "▶" else "⏸"
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        isRunning = false

        // Avisa a API que o overlay foi fechado e encerra a sessão ativa no servidor
        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
            ApiClient.clearPlayback()
        }

        overlayView?.let {
            try {
                windowManager?.removeView(it)
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
}
