package com.ficx.app.service

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import android.util.Base64
import kotlinx.coroutines.suspendCancellableCoroutine
import java.io.File
import kotlin.coroutines.resume

/**
 * Plays base64-encoded MP3 audio received from the server (AWS Polly output).
 * Each play() call is a suspend fun that resumes when playback completes.
 */
class AudioPlayer(private val context: Context) {

    private var current: MediaPlayer? = null
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    suspend fun playBase64Mp3(base64Data: String) = suspendCancellableCoroutine<Unit> { cont ->
        FiLog.i("AudioPlayer", "Decoding TTS audio (b64 len=${base64Data.length})")
        val bytes = try {
            Base64.decode(base64Data, Base64.DEFAULT)
        } catch (e: Exception) {
            FiLog.e("AudioPlayer", "Base64 decode failed", e)
            cont.resume(Unit)
            return@suspendCancellableCoroutine
        }

        val tmp = File(context.cacheDir, "tts_${System.currentTimeMillis()}.mp3")
        tmp.writeBytes(bytes)
        FiLog.i("AudioPlayer", "Playing ${bytes.size} bytes from ${tmp.name}")

        val mp = MediaPlayer()
        current = mp

        // Force loudspeaker and raise to max call volume for every TTS utterance
        audioManager.isSpeakerphoneOn = true
        val maxVol = audioManager.getStreamMaxVolume(AudioManager.STREAM_VOICE_CALL)
        audioManager.setStreamVolume(AudioManager.STREAM_VOICE_CALL, maxVol, 0)

        mp.setAudioAttributes(
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build()
        )

        fun cleanup() {
            try { mp.stop(); mp.release() } catch (_: Exception) {}
            tmp.delete()
            current = null
        }

        try {
            mp.setDataSource(tmp.absolutePath)
            mp.setOnCompletionListener {
                FiLog.d("AudioPlayer", "Playback complete")
                cleanup()
                if (cont.isActive) cont.resume(Unit)
            }
            mp.setOnErrorListener { _, what, extra ->
                FiLog.e("AudioPlayer", "MediaPlayer error what=$what extra=$extra")
                cleanup()
                if (cont.isActive) cont.resume(Unit)
                true
            }
            mp.prepare()
            mp.start()
        } catch (e: Exception) {
            FiLog.e("AudioPlayer", "Playback setup failed", e)
            cleanup()
            if (cont.isActive) cont.resume(Unit)
        }

        cont.invokeOnCancellation { cleanup() }
    }

    fun release() {
        try { current?.stop(); current?.release() } catch (_: Exception) {}
        current = null
    }
}
