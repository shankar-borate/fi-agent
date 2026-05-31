package com.ficx.app.service

import okhttp3.*
import okio.ByteString
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Manages a single OkHttp WebSocket connection to the FI session server.
 *
 * All callbacks are invoked on OkHttp's background dispatcher threads.
 * Call [connect] once, then use [sendJson] / [sendBinary], and [close] when done.
 */
class WebSocketManager(
    private val onMessage: (JSONObject) -> Unit,
    private val onOpen: () -> Unit = {},
    private val onFailure: (Throwable, String?) -> Unit = { _, _ -> },
    private val onClosed: (Int, String) -> Unit = { _, _ -> },
) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.SECONDS)    // no read timeout on long-lived WS
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    @Volatile private var ws: WebSocket? = null

    fun connect(url: String) {
        FiLog.i("WS", "Connecting → $url")
        val request = Request.Builder().url(url).build()
        ws = client.newWebSocket(request, Listener())
    }

    /** Send a JSON text frame. Returns false if not connected. */
    fun sendJson(payload: JSONObject): Boolean {
        val text = payload.toString()
        FiLog.d("WS", "→JSON ${text.take(140)}")
        return ws?.send(text) ?: false.also { FiLog.w("WS", "sendJson: no connection") }
    }

    /** Send raw binary frame (PCM audio chunk). */
    fun sendBinary(bytes: ByteArray): Boolean =
        ws?.send(bytes.toByteString()) ?: false

    fun close() {
        FiLog.i("WS", "Closing WebSocket")
        ws?.close(1000, "Session complete")
        ws = null
    }

    // ── OkHttp listener ───────────────────────────────────────────────────────

    private inner class Listener : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            FiLog.i("WS", "Connected — HTTP ${response.code}")
            onOpen()
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            FiLog.d("WS", "←JSON ${text.take(140)}")
            try {
                onMessage(JSONObject(text))
            } catch (e: Exception) {
                FiLog.e("WS", "JSON parse error: $e")
            }
        }

        override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
            // Server never sends binary currently; log if it does
            FiLog.d("WS", "←BIN ${bytes.size} bytes")
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            FiLog.e("WS", "Failure: ${t.message} — HTTP ${response?.code}", t)
            onFailure(t, response?.message)
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            FiLog.i("WS", "Closed: $code $reason")
            onClosed(code, reason)
        }
    }
}
