package com.ficx.app.ui

import android.media.AudioManager
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.ficx.app.databinding.ActivityFiSessionBinding
import com.ficx.app.service.FiLog
import com.ficx.app.service.SessionRecordingService
import com.ficx.app.ui.viewmodel.FiSessionViewModel
import com.ficx.app.ui.viewmodel.UiState
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import java.io.File
import java.text.SimpleDateFormat
import java.util.*
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class FiSessionActivity : AppCompatActivity() {

    private lateinit var binding: ActivityFiSessionBinding
    private val viewModel: FiSessionViewModel by viewModels()
    private lateinit var cameraExecutor: ExecutorService

    private var imageCapture: ImageCapture? = null
    private var currentLensFacing = CameraSelector.LENS_FACING_FRONT
    private lateinit var audioManager: AudioManager
    private var savedAudioMode = AudioManager.MODE_NORMAL

    private var pendingPhotoPrompt = ""
    private var pendingIsSelfie    = true
    private var pendingPhotoIndex  = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityFiSessionBinding.inflate(layoutInflater)
        setContentView(binding.root)
        FiLog.i("Session", "Activity created — case=${viewModel.caseId}")

        cameraExecutor = Executors.newSingleThreadExecutor()
        viewModel.init(this)

        enableLoudspeaker()
        startCamera(CameraSelector.LENS_FACING_FRONT)
        startAudioRecording()
        observeUiState()

        binding.btnSave.setOnClickListener    { viewModel.onSave() }
        binding.btnDiscard.setOnClickListener { viewModel.onDiscard() }

        binding.btnSubmit.setOnClickListener {
            binding.btnSubmit.isEnabled = false
            FiLog.i("Session", "Submit tapped")
            stopAudioRecording()
            lifecycleScope.launch {
                delay(600)  // let MediaRecorder.stop() flush
                viewModel.submitSession()
            }
        }

        viewModel.connect()
    }

    // ── UI State observer ─────────────────────────────────────────────────────

    private fun observeUiState() {
        lifecycleScope.launch {
            viewModel.uiState.collectLatest { state ->
                FiLog.d("Session", "UI → ${state::class.simpleName}")
                when (state) {

                    is UiState.Idle, is UiState.Connecting -> {
                        setMessage("Connecting to server…")
                        hideAll()
                    }

                    is UiState.ShowMessage -> {
                        setMessage(state.text)
                        hideAll()
                    }

                    is UiState.Listening -> {
                        setMessage("Listening… (Q${state.questionIndex + 1})")
                        showMic()
                        hideCountdown(); hideTranscript(); hideReviewButtons(); hideSubmit()
                        binding.progressBar.visibility = View.GONE
                    }

                    is UiState.ShowTranscript -> {
                        hideMic()
                        hideCountdown()
                        showTranscript(state.text, state.isFinal)
                        hideReviewButtons(); hideSubmit()
                        binding.progressBar.visibility = View.GONE
                    }

                    is UiState.Countdown -> {
                        setMessage(state.prompt)
                        showCountdown(state.remaining)
                        hideMic(); hideTranscript(); hideReviewButtons(); hideSubmit()
                        binding.progressBar.visibility = View.GONE
                    }

                    is UiState.CaptureNow -> {
                        hideAll()
                        pendingPhotoPrompt = state.prompt
                        pendingIsSelfie    = state.isSelfie
                        pendingPhotoIndex  = state.index

                        val needed = if (state.isSelfie) CameraSelector.LENS_FACING_FRONT
                                     else                CameraSelector.LENS_FACING_BACK
                        if (currentLensFacing != needed) {
                            currentLensFacing = needed
                            startCamera(needed)
                        }
                        setMessage("Taking photo…")
                        takePhoto()
                    }

                    is UiState.ReviewPhoto -> {
                        val label = if (state.isSelfie) "Selfie" else "Photo ${state.index + 1}"
                        setMessage("$label: ${state.prompt}")
                        showCountdown(state.remaining)
                        showReviewButtons()
                        hideMic(); hideTranscript(); hideSubmit()
                        binding.progressBar.visibility = View.GONE
                    }

                    is UiState.UploadingPhoto -> {
                        hideAll()
                        setMessage("Uploading photo ${state.index + 1}…")
                        binding.progressBar.visibility = View.VISIBLE
                    }

                    is UiState.ReadyToSubmit -> {
                        hideAll()
                        setMessage(
                            "Session ${state.caseId} complete\n" +
                            "${state.photoCount} photo(s)  •  " +
                            (if (state.hasRecording) "Recording ready" else "No recording") +
                            "\n\nTap Submit when ready."
                        )
                        showSubmit()
                        FiLog.i("Session", "ReadyToSubmit — ${state.caseId}")
                    }

                    is UiState.Uploading -> {
                        hideAll()
                        setMessage("Uploading session data…")
                        binding.progressBar.visibility = View.VISIBLE
                    }

                    is UiState.Done -> {
                        hideAll()
                        setMessage(state.message)
                        FiLog.i("Session", "Done: ${state.message}")
                        Toast.makeText(this@FiSessionActivity, state.message, Toast.LENGTH_LONG).show()
                        binding.root.postDelayed({ finish() }, 3_000)
                    }

                    is UiState.Error -> {
                        hideAll()
                        stopAudioRecording()
                        setMessage("Error: ${state.message}")
                        FiLog.e("Session", "Error: ${state.message}")
                        if (state.showRetry) {
                            showReviewButtons()  // Save = retry upload, Discard = skip photo
                        } else {
                            showSubmit()         // submit failure — retry via Submit button
                        }
                        Toast.makeText(this@FiSessionActivity, state.message, Toast.LENGTH_LONG).show()
                    }
                }
            }
        }
    }

    // ── Camera ────────────────────────────────────────────────────────────────

    private fun startCamera(lensFacing: Int) {
        FiLog.d("Session", "Camera facing=$lensFacing")
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            val provider = future.get()
            val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(binding.previewView.surfaceProvider)
            }
            imageCapture = ImageCapture.Builder()
                .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                .build()
            val selector = CameraSelector.Builder().requireLensFacing(lensFacing).build()
            try {
                provider.unbindAll()
                provider.bindToLifecycle(this, selector, preview, imageCapture)
            } catch (e: Exception) {
                FiLog.e("Session", "Camera bind failed", e)
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun takePhoto() {
        val ic = imageCapture ?: run { FiLog.e("Session", "ImageCapture not ready"); return }
        val ts   = SimpleDateFormat("yyyyMMdd_HHmmss_SSS", Locale.US).format(Date())
        val file = File(outputDir(), "photo_${ts}.jpg")

        val opts = ImageCapture.OutputFileOptions.Builder(file).build()
        ic.takePicture(opts, cameraExecutor, object : ImageCapture.OnImageSavedCallback {
            override fun onImageSaved(output: ImageCapture.OutputFileResults) {
                FiLog.i("Session", "Photo saved: ${file.name} (${file.length()} bytes)")
                viewModel.notifyPhotoCaptured(file, pendingPhotoPrompt, pendingIsSelfie, pendingPhotoIndex)
            }
            override fun onError(exc: ImageCaptureException) {
                FiLog.e("Session", "Photo error", exc)
                viewModel.notifyPhotoCaptureFailed(pendingPhotoIndex)
            }
        })
    }

    // ── Audio routing ─────────────────────────────────────────────────────────

    private fun enableLoudspeaker() {
        audioManager = getSystemService(AUDIO_SERVICE) as AudioManager
        savedAudioMode = audioManager.mode
        audioManager.mode = AudioManager.MODE_IN_COMMUNICATION
        audioManager.isSpeakerphoneOn = true
        val maxVol = audioManager.getStreamMaxVolume(AudioManager.STREAM_VOICE_CALL)
        audioManager.setStreamVolume(AudioManager.STREAM_VOICE_CALL, maxVol, 0)
    }

    private fun restoreAudio() {
        if (::audioManager.isInitialized) {
            audioManager.isSpeakerphoneOn = false
            audioManager.mode = savedAudioMode
        }
    }

    // ── Session audio recording ───────────────────────────────────────────────

    private fun startAudioRecording() {
        val ts      = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val recFile = File(outputDir(), "recording_${viewModel.caseId}_$ts.mp4")
        viewModel.recordingFile = recFile
        ContextCompat.startForegroundService(
            this, SessionRecordingService.startIntent(this, recFile.absolutePath)
        )
    }

    private fun stopAudioRecording() {
        startService(SessionRecordingService.stopIntent(this))
    }

    // ── UI helpers ────────────────────────────────────────────────────────────

    private fun hideAll() {
        hideMic(); hideCountdown(); hideTranscript(); hideReviewButtons(); hideSubmit()
        binding.progressBar.visibility = View.GONE
    }

    private fun setMessage(text: String) { binding.tvMessage.text = text }
    private fun showMic()               { binding.ivMicIndicator.visibility = View.VISIBLE }
    private fun hideMic()               { binding.ivMicIndicator.visibility = View.GONE }
    private fun showCountdown(n: Int)   { binding.tvCountdown.visibility = View.VISIBLE; binding.tvCountdown.text = n.toString() }
    private fun hideCountdown()         { binding.tvCountdown.visibility = View.GONE }
    private fun showTranscript(t: String, final: Boolean) {
        binding.tvTranscript.visibility = View.VISIBLE
        binding.tvTranscript.text  = if (final) "Answer: $t" else t
        binding.tvTranscript.alpha = if (final) 1.0f else 0.7f
    }
    private fun hideTranscript()        { binding.tvTranscript.visibility = View.GONE }
    private fun showReviewButtons()     { binding.layoutReviewButtons.visibility = View.VISIBLE }
    private fun hideReviewButtons()     { binding.layoutReviewButtons.visibility = View.GONE }
    private fun showSubmit()            { binding.btnSubmit.visibility = View.VISIBLE; binding.btnSubmit.isEnabled = true }
    private fun hideSubmit()            { binding.btnSubmit.visibility = View.GONE }

    private fun outputDir(): File =
        File(filesDir, "fi_sessions/${viewModel.caseId}").also { it.mkdirs() }

    override fun onDestroy() {
        super.onDestroy()
        restoreAudio()
        cameraExecutor.shutdown()
    }
}
