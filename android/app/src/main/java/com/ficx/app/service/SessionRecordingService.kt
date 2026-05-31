package com.ficx.app.service

import android.app.*
import android.content.Context
import android.content.Intent
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import java.io.File

/**
 * Foreground service that records microphone audio for the entire FI session.
 * Runs in a separate process-safe context so recording is not interrupted by
 * activity lifecycle events.
 */
class SessionRecordingService : Service() {

    private var recorder: MediaRecorder? = null
    private var outputFile: File? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIF_ID, buildNotification())
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                val path = intent.getStringExtra(EXTRA_OUTPUT_PATH) ?: return START_NOT_STICKY
                startRecording(File(path))
            }
            ACTION_STOP -> stopRecordingAndSelf()
        }
        return START_NOT_STICKY
    }

    private fun startRecording(file: File) {
        outputFile = file
        recorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            MediaRecorder(this)
        } else {
            @Suppress("DEPRECATION")
            MediaRecorder()
        }
        recorder?.apply {
            setAudioSource(MediaRecorder.AudioSource.MIC)
            setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            setAudioSamplingRate(44100)
            setAudioEncodingBitRate(128_000)
            setOutputFile(file.absolutePath)
            prepare()
            start()
        }
    }

    private fun stopRecordingAndSelf() {
        try {
            recorder?.stop()
            recorder?.release()
        } catch (_: Exception) {}
        recorder = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        super.onDestroy()
        try { recorder?.stop(); recorder?.release() } catch (_: Exception) {}
        recorder = null
    }

    private fun buildNotification(): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("FI Session Recording")
            .setContentText("Recording in progress…")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val chan = NotificationChannel(
                CHANNEL_ID, "FI Recording", NotificationManager.IMPORTANCE_LOW
            )
            getSystemService(NotificationManager::class.java).createNotificationChannel(chan)
        }
    }

    companion object {
        const val CHANNEL_ID = "fi_recording_channel"
        const val NOTIF_ID = 1001
        const val ACTION_START = "com.ficx.app.RECORDING_START"
        const val ACTION_STOP  = "com.ficx.app.RECORDING_STOP"
        const val EXTRA_OUTPUT_PATH = "output_path"

        fun startIntent(context: Context, outputPath: String) =
            Intent(context, SessionRecordingService::class.java).apply {
                action = ACTION_START
                putExtra(EXTRA_OUTPUT_PATH, outputPath)
            }

        fun stopIntent(context: Context) =
            Intent(context, SessionRecordingService::class.java).apply {
                action = ACTION_STOP
            }
    }
}
