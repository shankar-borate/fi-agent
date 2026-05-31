package com.ficx.app.service

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import kotlinx.coroutines.suspendCancellableCoroutine
import java.util.Locale
import kotlin.coroutines.resume

class TtsHelper(context: Context) {

    private var tts: TextToSpeech? = null
    private var ready = false

    init {
        tts = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.language = Locale.US
                ready = true
            }
        }
    }

    /** Speak text and suspend until utterance completes. */
    suspend fun speak(text: String) = suspendCancellableCoroutine { cont ->
        if (!ready) { cont.resume(Unit); return@suspendCancellableCoroutine }
        val id = "utt_${System.currentTimeMillis()}"
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {}
            override fun onDone(utteranceId: String?) {
                if (utteranceId == id && cont.isActive) cont.resume(Unit)
            }
            override fun onError(utteranceId: String?) {
                if (utteranceId == id && cont.isActive) cont.resume(Unit)
            }
        })
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, id)
        cont.invokeOnCancellation { tts?.stop() }
    }

    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        tts = null
    }
}
