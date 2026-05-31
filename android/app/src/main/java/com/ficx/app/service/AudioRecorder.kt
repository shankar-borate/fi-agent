package com.ficx.app.service

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import kotlinx.coroutines.*

/**
 * Streams raw PCM audio (16 kHz, 16-bit, mono) via [onChunk] callback.
 * Designed to feed AWS Transcribe through the WebSocket.
 *
 * Lifecycle: call [start] → send chunks until [stop] is called.
 */
class AudioRecorder {

    companion object {
        private const val SAMPLE_RATE    = 16_000
        private const val CHANNEL        = AudioFormat.CHANNEL_IN_MONO
        private const val ENCODING       = AudioFormat.ENCODING_PCM_16BIT
        private const val CHUNK_MILLIS   = 100           // 100 ms per chunk → 3 200 bytes
    }

    @Volatile private var recording = false
    private var record: AudioRecord? = null
    private var job: Job? = null

    @SuppressLint("MissingPermission")
    fun start(scope: CoroutineScope, onChunk: (ByteArray) -> Unit) {
        if (recording) return
        val minBuf = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL, ENCODING)
        val chunkBytes = SAMPLE_RATE * 2 * CHUNK_MILLIS / 1000

        record = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            SAMPLE_RATE, CHANNEL, ENCODING,
            maxOf(minBuf, chunkBytes * 4)
        )

        if (record?.state != AudioRecord.STATE_INITIALIZED) {
            FiLog.e("AudioRecorder", "AudioRecord init failed")
            return
        }

        recording = true
        record?.startRecording()
        FiLog.i("AudioRecorder", "Recording started — $SAMPLE_RATE Hz, $chunkBytes bytes/chunk")

        job = scope.launch(Dispatchers.IO) {
            val buf = ByteArray(chunkBytes)
            while (recording && isActive) {
                val read = record?.read(buf, 0, buf.size) ?: 0
                if (read > 0) {
                    onChunk(buf.copyOf(read))
                } else if (read < 0) {
                    FiLog.w("AudioRecorder", "AudioRecord error code: $read")
                    break
                }
            }
            FiLog.d("AudioRecorder", "Recording loop exited")
        }
    }

    fun stop() {
        if (!recording) return
        FiLog.i("AudioRecorder", "Stopping recording")
        recording = false
        job?.cancel()
        job = null
        try {
            record?.stop()
            record?.release()
        } catch (e: Exception) {
            FiLog.e("AudioRecorder", "Stop error", e)
        }
        record = null
    }
}
