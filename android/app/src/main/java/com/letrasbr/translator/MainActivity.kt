package com.letrasbr.translator

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.NotificationManagerCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var tvPermMedia: TextView
    private lateinit var btnGrantMedia: Button
    private lateinit var tvPermOverlay: TextView
    private lateinit var btnGrantOverlay: Button
    private lateinit var etApiUrl: EditText
    private lateinit var btnTestConn: Button
    private lateinit var tvConnStatus: TextView
    private lateinit var switchOverlay: Switch
    private lateinit var rgLang: RadioGroup

    private val prefs by lazy { getSharedPreferences("letrasbr_prefs", Context.MODE_PRIVATE) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        bindViews()
        loadSavedPreferences()
        setupListeners()
    }

    override fun onResume() {
        super.onResume()
        checkPermissions()
    }

    private fun bindViews() {
        tvPermMedia = findViewById(R.id.tv_perm_media)
        btnGrantMedia = findViewById(R.id.btn_grant_media)
        tvPermOverlay = findViewById(R.id.tv_perm_overlay)
        btnGrantOverlay = findViewById(R.id.btn_grant_overlay)
        etApiUrl = findViewById(R.id.et_api_url)
        btnTestConn = findViewById(R.id.btn_test_connection)
        tvConnStatus = findViewById(R.id.tv_connection_status)
        switchOverlay = findViewById(R.id.switch_overlay)
        rgLang = findViewById(R.id.rg_lang)
    }

    private fun loadSavedPreferences() {
        val savedUrl = prefs.getString("api_url", "http://192.168.1.15:8000") ?: "http://192.168.1.15:8000"
        etApiUrl.setText(savedUrl)
        ApiClient.baseUrl = savedUrl.trimEnd('/')

        val savedLang = prefs.getString("lang", "pt") ?: "pt"
        MediaListenerService.selectedLang = savedLang
        when (savedLang) {
            "en" -> findViewById<RadioButton>(R.id.rb_en).isChecked = true
            "es" -> findViewById<RadioButton>(R.id.rb_es).isChecked = true
            "fr" -> findViewById<RadioButton>(R.id.rb_fr).isChecked = true
            else -> findViewById<RadioButton>(R.id.rb_pt).isChecked = true
        }

        switchOverlay.isChecked = FloatingOverlayService.isRunning
    }

    private fun setupListeners() {
        // Conceder Permissão de Mídia / Notificação
        btnGrantMedia.setOnClickListener {
            startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
        }

        // Conceder Permissão de Janela Flutuante (Overlay)
        btnGrantOverlay.setOnClickListener {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                val intent = Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:$packageName")
                )
                startActivity(intent)
            }
        }

        // Testar Conexão com API
        btnTestConn.setOnClickListener {
            val url = etApiUrl.text.toString().trimEnd('/')
            if (url.isEmpty()) return@setOnClickListener

            ApiClient.baseUrl = url
            prefs.edit().putString("api_url", url).apply()

            tvConnStatus.text = "⏳ Testando conexão..."
            tvConnStatus.setTextColor(getColor(R.color.text_secondary))

            lifecycleScope.launch {
                val ok = ApiClient.checkHealth()
                if (ok) {
                    tvConnStatus.text = "🟢 Conexão com a API OK!"
                    tvConnStatus.setTextColor(getColor(R.color.success_green))
                } else {
                    tvConnStatus.text = "🔴 Falha ao conectar. Verifique o IP e a porta."
                    tvConnStatus.setTextColor(getColor(R.color.error_red))
                }
            }
        }

        // Ativar/Desativar Janela Flutuante
        switchOverlay.setOnCheckedChangeListener { _, isChecked ->
            if (isChecked) {
                if (checkOverlayPermission()) {
                    val intent = Intent(this, FloatingOverlayService::class.java)
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        startForegroundService(intent)
                    } else {
                        startService(intent)
                    }
                } else {
                    switchOverlay.isChecked = false
                    Toast.makeText(this, "Conceda a permissão de Janela Flutuante primeiro!", Toast.LENGTH_SHORT).show()
                }
            } else {
                stopService(Intent(this, FloatingOverlayService::class.java))
            }
        }

        // Seleção de Idioma
        rgLang.setOnCheckedChangeListener { _, checkedId ->
            val lang = when (checkedId) {
                R.id.rb_en -> "en"
                R.id.rb_es -> "es"
                R.id.rb_fr -> "fr"
                else -> "pt"
            }
            MediaListenerService.selectedLang = lang
            prefs.edit().putString("lang", lang).apply()
        }
    }

    private fun checkPermissions() {
        val hasMedia = checkMediaPermission()
        if (hasMedia) {
            tvPermMedia.text = "1. Leitura de Mídia: ✅ Concedido"
            tvPermMedia.setTextColor(getColor(R.color.success_green))
            btnGrantMedia.isEnabled = false
            btnGrantMedia.text = "OK"
        } else {
            tvPermMedia.text = "1. Leitura de Mídia: ⚠️ Pendente"
            tvPermMedia.setTextColor(getColor(R.color.error_red))
            btnGrantMedia.isEnabled = true
        }

        val hasOverlay = checkOverlayPermission()
        if (hasOverlay) {
            tvPermOverlay.text = "2. Janela Flutuante: ✅ Concedido"
            tvPermOverlay.setTextColor(getColor(R.color.success_green))
            btnGrantOverlay.isEnabled = false
            btnGrantOverlay.text = "OK"
        } else {
            tvPermOverlay.text = "2. Janela Flutuante: ⚠️ Pendente"
            tvPermOverlay.setTextColor(getColor(R.color.error_red))
            btnGrantOverlay.isEnabled = true
        }
    }

    private fun checkMediaPermission(): Boolean {
        val packages = NotificationManagerCompat.getEnabledListenerPackages(this)
        return packages.contains(packageName)
    }

    private fun checkOverlayPermission(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Settings.canDrawOverlays(this)
        } else {
            true
        }
    }
}
