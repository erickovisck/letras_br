package com.letrasbr.translator

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.IBinder
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.TextView
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

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

        fun refreshStyling() {
            instance?.applyStyling()
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
        applyStyling()

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
        val btnSettings = view.findViewById<TextView>(R.id.overlay_btn_settings)
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

        // Abrir Configurações / App
        btnSettings.setOnClickListener {
            val intent = Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
            }
            startActivity(intent)
        }

        // Fechar Overlay
        btnClose.setOnClickListener {
            stopSelf()
        }
    }

    fun applyStyling() {
        val view = overlayView ?: return
        view.post {
            val prefs = getSharedPreferences("letrasbr_prefs", Context.MODE_PRIVATE)

            val bgColorHex = prefs.getString("bg_color", "#121216") ?: "#121216"
            val opacityPct = prefs.getInt("opacity", 88)
            val origColorHex = prefs.getString("orig_color", "#CBD5E1") ?: "#CBD5E1"
            val transColorHex = prefs.getString("trans_color", "#38BDF8") ?: "#38BDF8"
            val fontSize = prefs.getInt("font_size", 15)
            val fontFamily = prefs.getString("font_family", "sans-serif") ?: "sans-serif"
            val fontBold = prefs.getBoolean("font_bold", true)
            val fontItalic = prefs.getBoolean("font_italic", false)
            val displayMode = prefs.getString("display_mode", "both") ?: "both"

            val root = view.findViewById<View>(R.id.overlay_root)
            val tvOrig = view.findViewById<TextView>(R.id.overlay_text_original)
            val tvTrans = view.findViewById<TextView>(R.id.overlay_text_translation)
            val btnPlay = view.findViewById<TextView>(R.id.overlay_btn_play)

            // 1. Fundo com cor + opacidade personalizada
            try {
                val baseColor = Color.parseColor(bgColorHex)
                val alpha = ((opacityPct / 100f) * 255).toInt().coerceIn(0, 255)
                val finalBgColor = Color.argb(alpha, Color.red(baseColor), Color.green(baseColor), Color.blue(baseColor))

                val accentColor = try { Color.parseColor(transColorHex) } catch (_: Exception) { Color.parseColor("#38BDF8") }
                val strokeColor = Color.argb(60, Color.red(accentColor), Color.green(accentColor), Color.blue(accentColor))

                val density = resources.displayMetrics.density
                val shape = GradientDrawable().apply {
                    shape = GradientDrawable.RECTANGLE
                    cornerRadius = 18 * density
                    setColor(finalBgColor)
                    setStroke((1.5 * density).toInt(), strokeColor)
                }
                root.background = shape
            } catch (e: Exception) {
                e.printStackTrace()
            }

            // 2. Tipografia e estilo
            val style = when {
                fontBold && fontItalic -> Typeface.BOLD_ITALIC
                fontBold -> Typeface.BOLD
                fontItalic -> Typeface.ITALIC
                else -> Typeface.NORMAL
            }
            val tf = try {
                Typeface.create(fontFamily, style)
            } catch (_: Exception) {
                Typeface.create(Typeface.DEFAULT, style)
            }

            // Letra Original
            try {
                tvOrig.setTextColor(Color.parseColor(origColorHex))
            } catch (_: Exception) {}
            tvOrig.textSize = fontSize.toFloat()
            tvOrig.typeface = tf

            // Letra Traduzida
            try {
                val transColor = Color.parseColor(transColorHex)
                tvTrans.setTextColor(transColor)
                btnPlay.setTextColor(transColor)
            } catch (_: Exception) {}
            tvTrans.textSize = (fontSize + 1).toFloat()
            tvTrans.typeface = tf

            // 3. Modos de Exibição
            when (displayMode) {
                "trans" -> {
                    tvOrig.visibility = View.GONE
                    tvTrans.visibility = View.VISIBLE
                }
                "orig" -> {
                    tvOrig.visibility = View.VISIBLE
                    tvTrans.visibility = View.GONE
                }
                else -> {
                    tvOrig.visibility = View.VISIBLE
                    tvTrans.visibility = View.VISIBLE
                }
            }
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
                btnPlay.text = if (isPaused) "▶" else "⏸"

                val newOrig = original.ifEmpty { "Aguardando versos..." }
                val newTrans = translation

                val changed = tvOrig.text.toString() != newOrig || tvTrans.text.toString() != newTrans
                if (changed) {
                    // Transição suave vertical inspirada no desktop
                    tvOrig.animate().alpha(0.2f).translationY(-6f).setDuration(110).withEndAction {
                        tvOrig.text = newOrig
                        tvOrig.animate().alpha(1.0f).translationY(0f).setDuration(150).start()
                    }.start()

                    tvTrans.animate().alpha(0.2f).translationY(-6f).setDuration(110).withEndAction {
                        tvTrans.text = newTrans
                        tvTrans.animate().alpha(1.0f).translationY(0f).setDuration(150).start()
                    }.start()
                }
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        isRunning = false

        // Avisa a API que o overlay foi fechado
        CoroutineScope(Dispatchers.IO).launch {
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
