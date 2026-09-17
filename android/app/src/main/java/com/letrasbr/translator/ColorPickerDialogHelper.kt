package com.letrasbr.translator

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.text.Editable
import android.text.TextWatcher
import android.view.LayoutInflater
import android.view.View
import android.widget.EditText
import android.widget.GridLayout
import androidx.appcompat.app.AlertDialog

object ColorPickerDialogHelper {

    private val PRESET_COLORS = listOf(
        "#121216", "#000000", "#0F172A", "#1E1B4B",
        "#38BDF8", "#06B6D4", "#10B981", "#22C55E",
        "#F59E0B", "#EF4444", "#EC4899", "#A855F7",
        "#FFFFFF", "#CBD5E1", "#94A3B8", "#64748B"
    )

    fun show(
        context: Context,
        title: String,
        initialColorHex: String,
        onColorSelected: (String) -> Unit
    ) {
        val dialogView = LayoutInflater.from(context).inflate(R.layout.dialog_color_picker, null)
        val previewView = dialogView.findViewById<View>(R.id.color_preview)
        val etHex = dialogView.findViewById<EditText>(R.id.et_hex_color)
        val gridLayout = dialogView.findViewById<GridLayout>(R.id.grid_presets)

        var selectedHex = if (initialColorHex.startsWith("#")) initialColorHex else "#$initialColorHex"
        etHex.setText(selectedHex)
        updatePreview(previewView, selectedHex)

        val density = context.resources.displayMetrics.density
        val buttonSize = (40 * density).toInt()
        val margin = (4 * density).toInt()

        for (preset in PRESET_COLORS) {
            val colorView = View(context).apply {
                val params = GridLayout.LayoutParams().apply {
                    width = buttonSize
                    height = buttonSize
                    setMargins(margin, margin, margin, margin)
                }
                layoutParams = params

                val shape = GradientDrawable().apply {
                    shape = GradientDrawable.OVAL
                    setColor(Color.parseColor(preset))
                    setStroke((1.5 * density).toInt(), Color.parseColor("#44FFFFFF"))
                }
                background = shape

                setOnClickListener {
                    selectedHex = preset
                    etHex.setText(preset)
                    updatePreview(previewView, selectedHex)
                }
            }
            gridLayout.addView(colorView)
        }

        etHex.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
            override fun afterTextChanged(s: Editable?) {
                val str = s?.toString()?.trim() ?: ""
                if (str.matches(Regex("^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{8})$"))) {
                    selectedHex = str
                    updatePreview(previewView, selectedHex)
                }
            }
        })

        AlertDialog.Builder(context)
            .setTitle(title)
            .setView(dialogView)
            .setPositiveButton("Confirmar") { _, _ ->
                onColorSelected(selectedHex)
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }

    private fun updatePreview(view: View, hex: String) {
        try {
            val parsed = Color.parseColor(hex)
            val density = view.context.resources.displayMetrics.density
            val shape = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                cornerRadius = 8 * density
                setColor(parsed)
                setStroke((1 * density).toInt(), Color.WHITE)
            }
            view.background = shape
        } catch (_: Exception) {}
    }
}
