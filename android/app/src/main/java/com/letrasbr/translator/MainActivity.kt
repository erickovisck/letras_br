package com.letrasbr.translator

import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.NotificationManagerCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    // Controles Básicos & Permissões
    private lateinit var tvPermMedia: TextView
    private lateinit var btnGrantMedia: Button
    private lateinit var tvPermOverlay: TextView
    private lateinit var btnGrantOverlay: Button
    private lateinit var etApiUrl: EditText
    private lateinit var btnTestConn: Button
    private lateinit var tvConnStatus: TextView
    private lateinit var btnToggleOverlay: com.google.android.material.button.MaterialButton
    private lateinit var rgLang: RadioGroup

    // Controles de Estilização & Personalização
    private lateinit var previewContainer: View
    private lateinit var previewOrig: TextView
    private lateinit var previewTrans: TextView
    private lateinit var viewBgColorIndicator: View
    private lateinit var btnPickBgColor: Button
    private lateinit var tvOpacityLabel: TextView
    private lateinit var sbOpacity: SeekBar
    private lateinit var viewTransColorIndicator: View
    private lateinit var btnPickTransColor: Button
    private lateinit var viewOrigColorIndicator: View
    private lateinit var btnPickOrigColor: Button
    private lateinit var btnFontDec: Button
    private lateinit var btnFontInc: Button
    private lateinit var tvFontSizeVal: TextView
    private lateinit var sbFontSize: SeekBar
    private lateinit var spFontFamily: Spinner
    private lateinit var cbFontBold: CheckBox
    private lateinit var cbFontItalic: CheckBox
    private lateinit var rgDisplayMode: RadioGroup
    private lateinit var btnResetStyles: Button

    // Estado das preferências de estilo
    private var curBgColor = "#121216"
    private var curOpacity = 88
    private var curOrigColor = "#CBD5E1"
    private var curTransColor = "#38BDF8"
    private var curFontSize = 15
    private var curFontFamily = "sans-serif"
    private var curFontBold = true
    private var curFontItalic = false
    private var curDisplayMode = "both"

    private val fontFamilies = listOf("sans-serif", "serif", "monospace", "casual", "cursive")

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
        updateOverlayButtonState()
        refreshLivePreview()
    }

    private fun bindViews() {
        tvPermMedia = findViewById(R.id.tv_perm_media)
        btnGrantMedia = findViewById(R.id.btn_grant_media)
        tvPermOverlay = findViewById(R.id.tv_perm_overlay)
        btnGrantOverlay = findViewById(R.id.btn_grant_overlay)
        etApiUrl = findViewById(R.id.et_api_url)
        btnTestConn = findViewById(R.id.btn_test_connection)
        tvConnStatus = findViewById(R.id.tv_connection_status)
        btnToggleOverlay = findViewById(R.id.btn_toggle_overlay)
        rgLang = findViewById(R.id.rg_lang)

        // Estilização
        previewContainer = findViewById(R.id.preview_container)
        previewOrig = findViewById(R.id.preview_orig)
        previewTrans = findViewById(R.id.preview_trans)
        viewBgColorIndicator = findViewById(R.id.view_bg_color_indicator)
        btnPickBgColor = findViewById(R.id.btn_pick_bg_color)
        tvOpacityLabel = findViewById(R.id.tv_opacity_label)
        sbOpacity = findViewById(R.id.sb_opacity)
        viewTransColorIndicator = findViewById(R.id.view_trans_color_indicator)
        btnPickTransColor = findViewById(R.id.btn_pick_trans_color)
        viewOrigColorIndicator = findViewById(R.id.view_orig_color_indicator)
        btnPickOrigColor = findViewById(R.id.btn_pick_orig_color)
        btnFontDec = findViewById(R.id.btn_font_dec)
        btnFontInc = findViewById(R.id.btn_font_inc)
        tvFontSizeVal = findViewById(R.id.tv_font_size_val)
        sbFontSize = findViewById(R.id.sb_font_size)
        spFontFamily = findViewById(R.id.sp_font_family)
        cbFontBold = findViewById(R.id.cb_font_bold)
        cbFontItalic = findViewById(R.id.cb_font_italic)
        rgDisplayMode = findViewById(R.id.rg_display_mode)
        btnResetStyles = findViewById(R.id.btn_reset_styles)

        // Configura adaptador do spinner de fontes
        val adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, fontFamilies)
        spFontFamily.adapter = adapter
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

        // Estilização
        curBgColor = prefs.getString("bg_color", "#121216") ?: "#121216"
        curOpacity = prefs.getInt("opacity", 88)
        curOrigColor = prefs.getString("orig_color", "#CBD5E1") ?: "#CBD5E1"
        curTransColor = prefs.getString("trans_color", "#38BDF8") ?: "#38BDF8"
        curFontSize = prefs.getInt("font_size", 15)
        curFontFamily = prefs.getString("font_family", "sans-serif") ?: "sans-serif"
        curFontBold = prefs.getBoolean("font_bold", true)
        curFontItalic = prefs.getBoolean("font_italic", false)
        curDisplayMode = prefs.getString("display_mode", "both") ?: "both"

        // Atualiza controles visuais
        sbOpacity.progress = curOpacity
        tvOpacityLabel.text = "Opacidade: $curOpacity%"

        sbFontSize.progress = (curFontSize - 10).coerceIn(0, 18)
        tvFontSizeVal.text = "$curFontSize sp"

        val fontIndex = fontFamilies.indexOf(curFontFamily).coerceAtLeast(0)
        spFontFamily.setSelection(fontIndex)

        cbFontBold.isChecked = curFontBold
        cbFontItalic.isChecked = curFontItalic

        when (curDisplayMode) {
            "trans" -> findViewById<RadioButton>(R.id.rb_mode_trans).isChecked = true
            "orig" -> findViewById<RadioButton>(R.id.rb_mode_orig).isChecked = true
            else -> findViewById<RadioButton>(R.id.rb_mode_both).isChecked = true
        }

        refreshLivePreview()
        updateOverlayButtonState()
    }

    private fun refreshLivePreview() {
        // Atualiza indicadores de cores
        updateColorIndicator(viewBgColorIndicator, curBgColor)
        updateColorIndicator(viewTransColorIndicator, curTransColor)
        updateColorIndicator(viewOrigColorIndicator, curOrigColor)

        // 1. Fundo do preview com opacidade
        try {
            val baseColor = Color.parseColor(curBgColor)
            val alpha = ((curOpacity / 100f) * 255).toInt().coerceIn(0, 255)
            val finalBgColor = Color.argb(alpha, Color.red(baseColor), Color.green(baseColor), Color.blue(baseColor))

            val accentColor = try { Color.parseColor(curTransColor) } catch (_: Exception) { Color.parseColor("#38BDF8") }
            val strokeColor = Color.argb(60, Color.red(accentColor), Color.green(accentColor), Color.blue(accentColor))

            val density = resources.displayMetrics.density
            val shape = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                cornerRadius = 14 * density
                setColor(finalBgColor)
                setStroke((1.5 * density).toInt(), strokeColor)
            }
            previewContainer.background = shape
        } catch (e: Exception) {
            e.printStackTrace()
        }

        // 2. Tipografia e estilo
        val style = when {
            curFontBold && curFontItalic -> Typeface.BOLD_ITALIC
            curFontBold -> Typeface.BOLD
            curFontItalic -> Typeface.ITALIC
            else -> Typeface.NORMAL
        }
        val tf = try {
            Typeface.create(curFontFamily, style)
        } catch (_: Exception) {
            Typeface.create(Typeface.DEFAULT, style)
        }

        try {
            previewOrig.setTextColor(Color.parseColor(curOrigColor))
        } catch (_: Exception) {}
        previewOrig.textSize = curFontSize.toFloat()
        previewOrig.typeface = tf

        try {
            previewTrans.setTextColor(Color.parseColor(curTransColor))
        } catch (_: Exception) {}
        previewTrans.textSize = (curFontSize + 1).toFloat()
        previewTrans.typeface = tf

        // 3. Modos de Exibição no preview
        when (curDisplayMode) {
            "trans" -> {
                previewOrig.visibility = View.GONE
                previewTrans.visibility = View.VISIBLE
            }
            "orig" -> {
                previewOrig.visibility = View.VISIBLE
                previewTrans.visibility = View.GONE
            }
            else -> {
                previewOrig.visibility = View.VISIBLE
                previewTrans.visibility = View.VISIBLE
            }
        }
    }

    private fun updateColorIndicator(view: View, hex: String) {
        try {
            val parsed = Color.parseColor(hex)
            val density = resources.displayMetrics.density
            val shape = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(parsed)
                setStroke((1.5 * density).toInt(), Color.WHITE)
            }
            view.background = shape
        } catch (_: Exception) {}
    }

    private fun saveAndBroadcastStyles() {
        prefs.edit()
            .putString("bg_color", curBgColor)
            .putInt("opacity", curOpacity)
            .putString("orig_color", curOrigColor)
            .putString("trans_color", curTransColor)
            .putInt("font_size", curFontSize)
            .putString("font_family", curFontFamily)
            .putBoolean("font_bold", curFontBold)
            .putBoolean("font_italic", curFontItalic)
            .putString("display_mode", curDisplayMode)
            .apply()

        refreshLivePreview()
        FloatingOverlayService.refreshStyling()
    }

    private fun updateOverlayButtonState() {
        if (FloatingOverlayService.isRunning) {
            btnToggleOverlay.text = "Fechar Janela Flutuante"
            btnToggleOverlay.backgroundTintList = androidx.core.content.ContextCompat.getColorStateList(this, R.color.error_red)
        } else {
            btnToggleOverlay.text = "Abrir Janela Flutuante"
            btnToggleOverlay.backgroundTintList = androidx.core.content.ContextCompat.getColorStateList(this, R.color.accent_primary)
        }
    }

    private fun setupListeners() {
        // Permissões
        btnGrantMedia.setOnClickListener {
            startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
        }

        btnGrantOverlay.setOnClickListener {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                val intent = Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:$packageName")
                )
                startActivity(intent)
            }
        }

        // Testar Conexão
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
                    val savedLang = prefs.getString("lang", "pt") ?: "pt"
                    ApiClient.changeLanguage(savedLang)
                } else {
                    tvConnStatus.text = "🔴 Falha ao conectar. Verifique o IP e a porta."
                    tvConnStatus.setTextColor(getColor(R.color.error_red))
                }
            }
        }

        // Toggle Overlay
        btnToggleOverlay.setOnClickListener {
            if (FloatingOverlayService.isRunning) {
                stopService(Intent(this, FloatingOverlayService::class.java))
                lifecycleScope.launch {
                    ApiClient.clearPlayback()
                }
                btnToggleOverlay.postDelayed({ updateOverlayButtonState() }, 150)
            } else {
                if (checkOverlayPermission()) {
                    val intent = Intent(this, FloatingOverlayService::class.java)
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        startForegroundService(intent)
                    } else {
                        startService(intent)
                    }
                    btnToggleOverlay.postDelayed({ updateOverlayButtonState() }, 150)
                } else {
                    Toast.makeText(this, "Conceda a permissão de Janela Flutuante primeiro!", Toast.LENGTH_SHORT).show()
                }
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

            lifecycleScope.launch {
                val ok = ApiClient.changeLanguage(lang)
                if (ok) {
                    Toast.makeText(this@MainActivity, "Idioma alterado para ${lang.uppercase()} no servidor!", Toast.LENGTH_SHORT).show()
                }
            }
        }

        // Escolher Cor de Fundo
        btnPickBgColor.setOnClickListener {
            ColorPickerDialogHelper.show(this, "Escolher Cor do Fundo", curBgColor) { newColor ->
                curBgColor = newColor
                saveAndBroadcastStyles()
            }
        }

        // Opacidade
        sbOpacity.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                if (fromUser) {
                    curOpacity = progress.coerceIn(20, 100)
                    tvOpacityLabel.text = "Opacidade: $curOpacity%"
                    saveAndBroadcastStyles()
                }
            }
            override fun onStartTrackingTouch(seekBar: SeekBar?) {}
            override fun onStopTrackingTouch(seekBar: SeekBar?) {}
        })

        // Escolher Cor Tradução
        btnPickTransColor.setOnClickListener {
            ColorPickerDialogHelper.show(this, "Cor da Tradução", curTransColor) { newColor ->
                curTransColor = newColor
                saveAndBroadcastStyles()
            }
        }

        // Escolher Cor Original
        btnPickOrigColor.setOnClickListener {
            ColorPickerDialogHelper.show(this, "Cor da Letra Original", curOrigColor) { newColor ->
                curOrigColor = newColor
                saveAndBroadcastStyles()
            }
        }

        // Controles de Tamanho de Fonte ([−], [+], SeekBar)
        btnFontDec.setOnClickListener {
            if (curFontSize > 10) {
                curFontSize--
                tvFontSizeVal.text = "$curFontSize sp"
                sbFontSize.progress = (curFontSize - 10).coerceIn(0, 18)
                saveAndBroadcastStyles()
            }
        }

        btnFontInc.setOnClickListener {
            if (curFontSize < 28) {
                curFontSize++
                tvFontSizeVal.text = "$curFontSize sp"
                sbFontSize.progress = (curFontSize - 10).coerceIn(0, 18)
                saveAndBroadcastStyles()
            }
        }

        sbFontSize.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                if (fromUser) {
                    curFontSize = (progress + 10).coerceIn(10, 28)
                    tvFontSizeVal.text = "$curFontSize sp"
                    saveAndBroadcastStyles()
                }
            }
            override fun onStartTrackingTouch(seekBar: SeekBar?) {}
            override fun onStopTrackingTouch(seekBar: SeekBar?) {}
        })

        // Família da Fonte
        spFontFamily.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                val selected = fontFamilies.getOrElse(position) { "sans-serif" }
                if (selected != curFontFamily) {
                    curFontFamily = selected
                    saveAndBroadcastStyles()
                }
            }
            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }

        // Negrito & Itálico
        cbFontBold.setOnCheckedChangeListener { _, isChecked ->
            curFontBold = isChecked
            saveAndBroadcastStyles()
        }

        cbFontItalic.setOnCheckedChangeListener { _, isChecked ->
            curFontItalic = isChecked
            saveAndBroadcastStyles()
        }

        // Modos de Exibição
        rgDisplayMode.setOnCheckedChangeListener { _, checkedId ->
            curDisplayMode = when (checkedId) {
                R.id.rb_mode_trans -> "trans"
                R.id.rb_mode_orig -> "orig"
                else -> "both"
            }
            saveAndBroadcastStyles()
        }

        // Resetar Estilos
        btnResetStyles.setOnClickListener {
            curBgColor = "#121216"
            curOpacity = 88
            curOrigColor = "#CBD5E1"
            curTransColor = "#38BDF8"
            curFontSize = 15
            curFontFamily = "sans-serif"
            curFontBold = true
            curFontItalic = false
            curDisplayMode = "both"

            sbOpacity.progress = 88
            tvOpacityLabel.text = "Opacidade: 88%"
            sbFontSize.progress = 5
            tvFontSizeVal.text = "15 sp"
            spFontFamily.setSelection(0)
            cbFontBold.isChecked = true
            cbFontItalic.isChecked = false
            findViewById<RadioButton>(R.id.rb_mode_both).isChecked = true

            saveAndBroadcastStyles()
            Toast.makeText(this, "Estilos restaurados para os padrões!", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        if (!FloatingOverlayService.isRunning) {
            kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
                ApiClient.clearPlayback()
            }
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
