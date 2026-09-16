package com.letrasbr.translator

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

object ApiClient {

    var baseUrl: String = "http://10.0.2.2:8000" // Padrão ou configurável

    suspend fun checkHealth(): Boolean = withContext(Dispatchers.IO) {
        try {
            val url = URL("$baseUrl/api/health")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.connectTimeout = 3000
            conn.readTimeout = 3000
            val code = conn.responseCode
            conn.disconnect()
            code == 200
        } catch (e: Exception) {
            false
        }
    }

    suspend fun syncPlayback(
        title: String,
        artist: String,
        currentTimeSec: Double,
        durationSec: Double,
        isPaused: Boolean,
        lang: String = "pt",
        source: String = "ytmusic",
        trackId: String? = null
    ): SyncResult? = withContext(Dispatchers.IO) {
        try {
            val url = URL("$baseUrl/api/sync")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.connectTimeout = 2500
            conn.readTimeout = 2500

            val json = JSONObject().apply {
                put("title", title)
                put("artist", artist)
                put("currentTime", currentTimeSec)
                put("duration", durationSec)
                put("isPaused", isPaused)
                put("lang", lang)
                put("source", source)
                if (!trackId.isNullOrEmpty()) {
                    put("trackId", trackId)
                }
            }

            OutputStreamWriter(conn.outputStream).use { it.write(json.toString()) }

            if (conn.responseCode == 200) {
                val responseText = BufferedReader(InputStreamReader(conn.inputStream)).use { it.readText() }
                val respJson = JSONObject(responseText)
                SyncResult(
                    original = respJson.optString("activeOriginal", ""),
                    translation = respJson.optString("activeTranslation", ""),
                    command = if (respJson.has("command")) respJson.getString("command") else null
                )
            } else {
                null
            }
        } catch (e: Exception) {
            null
        }
    }

    suspend fun sendPlayerAction(action: String): Boolean = withContext(Dispatchers.IO) {
        try {
            val url = URL("$baseUrl/api/player/action")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.connectTimeout = 2000

            val json = JSONObject().apply { put("action", action) }
            OutputStreamWriter(conn.outputStream).use { it.write(json.toString()) }
            conn.responseCode == 200
        } catch (e: Exception) {
            false
        }
    }

    suspend fun changeLanguage(lang: String): Boolean = withContext(Dispatchers.IO) {
        try {
            val url = URL("$baseUrl/api/language")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.connectTimeout = 2500
            conn.readTimeout = 2500

            val json = JSONObject().apply { put("lang", lang) }
            OutputStreamWriter(conn.outputStream).use { it.write(json.toString()) }
            conn.responseCode == 200
        } catch (e: Exception) {
            false
        }
    }

    suspend fun clearPlayback(): Boolean = withContext(Dispatchers.IO) {
        try {
            val url = URL("$baseUrl/api/playback/clear")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.connectTimeout = 2500
            conn.readTimeout = 2500
            conn.responseCode == 200
        } catch (e: Exception) {
            false
        }
    }
}

data class SyncResult(
    val original: String,
    val translation: String,
    val command: String?
)
