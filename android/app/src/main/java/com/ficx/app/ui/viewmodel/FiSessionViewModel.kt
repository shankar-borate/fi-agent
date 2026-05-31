package com.ficx.app.ui.viewmodel

import android.content.Context
import android.provider.Settings
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.ficx.app.config.FiConfig
import com.ficx.app.data.repository.FiSessionRepository
import com.ficx.app.domain.model.FiSession
import com.ficx.app.domain.model.GeoPoint
import com.ficx.app.domain.model.PhotoCapture
import com.ficx.app.domain.model.QuestionAnswer
import com.ficx.app.service.*
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.*
import kotlin.coroutines.resume

// ── UI states ─────────────────────────────────────────────────────────────────

sealed class UiState {
    object Idle : UiState()
    object Connecting : UiState()
    data class ShowMessage(val text: String) : UiState()
    data class Listening(val questionIndex: Int) : UiState()
    data class ShowTranscript(val text: String, val isFinal: Boolean) : UiState()
    data class Countdown(val remaining: Int, val prompt: String) : UiState()
    data class CaptureNow(val isSelfie: Boolean, val index: Int, val prompt: String) : UiState()
    data class ReviewPhoto(
        val file: File,
        val prompt: String,
        val isSelfie: Boolean,
        val index: Int,
        val remaining: Int
    ) : UiState()
    data class UploadingPhoto(val index: Int) : UiState()
    data class ReadyToSubmit(val caseId: String, val photoCount: Int, val hasRecording: Boolean) : UiState()
    object Uploading : UiState()
    data class Done(val message: String) : UiState()
    /**
     * [showRetry] = true  → photo upload failure; Save = retry, Discard = skip
     * [showRetry] = false → final submit failure; show Submit button to retry
     */
    data class Error(val message: String, val showRetry: Boolean = false) : UiState()
}

// ── ViewModel ─────────────────────────────────────────────────────────────────

class FiSessionViewModel : ViewModel() {

    private val config = FiConfig.DEFAULT
    private val repo   = FiSessionRepository(config)
    private val iso    = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)

    private val _uiState = MutableStateFlow<UiState>(UiState.Idle)
    val uiState: StateFlow<UiState> = _uiState

    val caseId: String = (100000..999999).random().toString()
    private val startedAt = iso.format(Date())
    private var deviceId  = "unknown"

    var recordingFile: File? = null

    private val collectedAnswers = mutableListOf<QuestionAnswer>()
    private val collectedPhotos  = mutableListOf<PhotoCapture>()

    // Current question context — needed for repeat-on-empty-transcript
    private var currentQuestion      = ""
    private var currentQuestionIndex = -1
    private var lastQuestionAudio    = ""   // cached AWS Polly base64 for repeat
    private var pendingAnswerGeo: GeoPoint? = null
    private var pendingPhotoGeo:  GeoPoint? = null
    private var lastPrompt = ""

    // Photo review state
    private var reviewPhotoFile:     File?   = null
    private var reviewPhotoPrompt:   String  = ""
    private var reviewPhotoIsSelfie: Boolean = false
    private var reviewPhotoIndex:    Int     = 0

    private var reviewJob: Job? = null
    private var listenJob: Job? = null

    // Services
    private lateinit var wsManager:      WebSocketManager
    private lateinit var locationHelper: LocationHelper
    private lateinit var audioPlayer:    AudioPlayer
    private val audioRecorder =          AudioRecorder()

    // Android TTS — fallback when server doesn't include AWS Polly audio
    private var tts: TextToSpeech? = null
    private var ttsReady = false

    // ── Init ─────────────────────────────────────────────────────────────────

    fun init(context: Context) {
        locationHelper = LocationHelper(context)
        audioPlayer    = AudioPlayer(context)
        deviceId = Settings.Secure.getString(
            context.contentResolver, Settings.Secure.ANDROID_ID
        ) ?: "unknown"

        tts = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val r = tts?.setLanguage(Locale("en", "IN")) ?: TextToSpeech.LANG_MISSING_DATA
                ttsReady = r != TextToSpeech.LANG_MISSING_DATA && r != TextToSpeech.LANG_NOT_SUPPORTED
                FiLog.i("ViewModel", "Android TTS ready=$ttsReady (fallback)")
            }
        }
        FiLog.i("ViewModel", "Case $caseId  device $deviceId")
    }

    // ── TTS: AWS Polly via AudioPlayer (preferred) or Android TTS (fallback) ─

    private suspend fun speak(text: String, base64Audio: String = "") {
        if (base64Audio.isNotEmpty()) {
            audioPlayer.playBase64Mp3(base64Audio)
        } else if (ttsReady) {
            speakAndroid(text)
        }
    }

    private suspend fun speakAndroid(text: String) = suspendCancellableCoroutine<Unit> { cont ->
        val uid = UUID.randomUUID().toString()
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(id: String?) {}
            override fun onDone(id: String?)  { if (cont.isActive) cont.resume(Unit) }
            override fun onError(id: String?) { if (cont.isActive) cont.resume(Unit) }
        })
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, uid)
        cont.invokeOnCancellation { tts?.stop() }
    }

    // ── WebSocket connection ──────────────────────────────────────────────────

    fun connect() {
        val wsUrl = config.serverUrl
            .replace("http://", "ws://")
            .replace("https://", "wss://")
            .trimEnd('/') + "/ws/fi-session/$caseId"

        FiLog.i("ViewModel", "Connecting WS → $wsUrl")
        _uiState.value = UiState.Connecting

        wsManager = WebSocketManager(
            onMessage = { json -> handleServerMessage(json) },
            onOpen = {
                FiLog.i("ViewModel", "WS open — sending ready")
                viewModelScope.launch {
                    wsManager.sendJson(JSONObject().apply {
                        put("type",       "ready")
                        put("session_id", caseId)
                        put("device_id",  deviceId)
                        put("started_at", startedAt)
                    })
                }
            },
            onFailure = { t, _ ->
                FiLog.e("ViewModel", "WS failure: ${t.message}", t)
                _uiState.value = UiState.Error("Connection failed: ${t.message}")
            },
            onClosed = { code, reason ->
                FiLog.i("ViewModel", "WS closed $code $reason")
            }
        )
        wsManager.connect(wsUrl)
    }

    // ── Server → Android message handler ─────────────────────────────────────

    private fun handleServerMessage(json: JSONObject) {
        viewModelScope.launch {
            val type = json.optString("type")
            FiLog.i("ViewModel", "Server msg: $type")

            when (type) {

                "question" -> {
                    currentQuestion      = json.getString("text")
                    currentQuestionIndex = json.optInt("index", 0)
                    lastQuestionAudio    = json.optString("audio", "") // AWS Polly base64 if provided
                    FiLog.i("ViewModel", "Q${currentQuestionIndex + 1}: $currentQuestion")
                    lastPrompt = currentQuestion
                    _uiState.value = UiState.ShowMessage(currentQuestion)
                    speak(currentQuestion, lastQuestionAudio)
                    wsManager.sendJson(JSONObject().put("type", "tts_done"))
                }

                "start_listening" -> {
                    val qIdx      = json.optInt("question_index", 0)
                    val timeoutMs = json.optLong("timeout_ms", config.sttTimeoutMs)
                    FiLog.i("ViewModel", "Listen Q$qIdx timeout=${timeoutMs}ms")

                    pendingAnswerGeo = locationHelper.getLocation()
                    _uiState.value   = UiState.Listening(qIdx)
                    audioRecorder.start(viewModelScope) { chunk -> wsManager.sendBinary(chunk) }

                    listenJob?.cancel()
                    listenJob = viewModelScope.launch {
                        delay(timeoutMs)
                        FiLog.i("ViewModel", "Listen timeout → audio_end")
                        audioRecorder.stop()
                        wsManager.sendJson(JSONObject().put("type", "audio_end"))
                    }
                }

                "transcript" -> {
                    val text    = json.optString("text", "")
                    val isFinal = json.optBoolean("is_final", false)
                    FiLog.i("ViewModel", "Transcript final=$isFinal: '$text'")

                    if (isFinal) {
                        if (text.isBlank()) {
                            // No speech detected in 5 seconds — repeat the question
                            FiLog.i("ViewModel", "Empty answer — repeating Q$currentQuestionIndex")
                            _uiState.value = UiState.ShowMessage(currentQuestion)
                            speak(currentQuestion, lastQuestionAudio)
                            wsManager.sendJson(JSONObject().put("type", "tts_done"))
                        } else {
                            // Good answer received — store it
                            collectedAnswers += QuestionAnswer(
                                question = currentQuestion,
                                answer   = text,
                                geo      = pendingAnswerGeo
                            )
                            pendingAnswerGeo = null
                            FiLog.i("ViewModel", "Answer saved [${collectedAnswers.size}]: $text")
                            _uiState.value = UiState.ShowTranscript(text, true)
                        }
                    } else {
                        _uiState.value = UiState.ShowTranscript(text, false)
                    }
                }

                "announce_photo" -> {
                    val prompt = json.getString("prompt")
                    val audio  = json.optString("audio", "")
                    lastPrompt = prompt
                    FiLog.i("ViewModel", "Announce photo: $prompt")
                    _uiState.value = UiState.ShowMessage(prompt)
                    speak(prompt, audio)
                    wsManager.sendJson(JSONObject().put("type", "tts_done"))
                }

                "countdown" -> {
                    _uiState.value = UiState.Countdown(json.getInt("value"), lastPrompt)
                }

                "capture_photo" -> {
                    val prompt     = json.getString("prompt")
                    val isSelfie   = json.getBoolean("is_selfie")
                    val photoIndex = json.getInt("photo_index")
                    FiLog.i("ViewModel", "Capture selfie=$isSelfie idx=$photoIndex")
                    pendingPhotoGeo      = locationHelper.getLocation()
                    reviewPhotoPrompt    = prompt
                    reviewPhotoIsSelfie  = isSelfie
                    reviewPhotoIndex     = photoIndex
                    _uiState.value = UiState.CaptureNow(isSelfie, photoIndex, prompt)
                }

                "photo_ack" -> {
                    FiLog.d("ViewModel", "Photo ack idx=${json.optInt("photo_index")}")
                }

                "session_done" -> {
                    val msg = json.optString("message", "Session complete")
                    FiLog.i("ViewModel", "Session done: $msg")
                    wsManager.close()
                    _uiState.value = UiState.ReadyToSubmit(
                        caseId       = caseId,
                        photoCount   = collectedPhotos.size,
                        hasRecording = recordingFile != null
                    )
                }

                "error" -> {
                    val msg = json.optString("message", "Server error")
                    FiLog.e("ViewModel", "Server error: $msg")
                    _uiState.value = UiState.Error(msg)
                }

                else -> FiLog.w("ViewModel", "Unknown msg type: $type")
            }
        }
    }

    // ── Photo review (5-second countdown + Save / Discard) ───────────────────

    fun notifyPhotoCaptured(file: File, prompt: String, isSelfie: Boolean, photoIndex: Int) {
        reviewPhotoFile = file
        startPhotoReview()
    }

    fun notifyPhotoCaptureFailed(photoIndex: Int) {
        FiLog.w("ViewModel", "Capture failed idx=$photoIndex — retaking")
        viewModelScope.launch {
            _uiState.value = UiState.CaptureNow(reviewPhotoIsSelfie, reviewPhotoIndex, reviewPhotoPrompt)
        }
    }

    private fun startPhotoReview() {
        reviewJob?.cancel()
        val file = reviewPhotoFile ?: return
        reviewJob = viewModelScope.launch {
            for (i in 5 downTo 1) {
                _uiState.value = UiState.ReviewPhoto(
                    file, reviewPhotoPrompt, reviewPhotoIsSelfie, reviewPhotoIndex, i
                )
                delay(1_000)
            }
            FiLog.i("ViewModel", "Photo review timed out — auto-saving")
            commitPhoto()
        }
    }

    fun onSave() {
        when (val s = uiState.value) {
            is UiState.ReviewPhoto -> { reviewJob?.cancel(); viewModelScope.launch { commitPhoto() } }
            is UiState.Error       -> if (s.showRetry) retryPhotoUpload()
            else                   -> {}
        }
    }

    fun onDiscard() {
        when (val s = uiState.value) {
            is UiState.ReviewPhoto -> { reviewJob?.cancel(); discardPhoto() }
            is UiState.Error       -> if (s.showRetry) skipPhotoAndContinue()
            else                   -> {}
        }
    }

    private fun discardPhoto() {
        FiLog.i("ViewModel", "Photo discarded — retaking")
        viewModelScope.launch {
            _uiState.value = UiState.ShowMessage("Retaking photo…")
            delay(300)
            _uiState.value = UiState.CaptureNow(reviewPhotoIsSelfie, reviewPhotoIndex, reviewPhotoPrompt)
        }
    }

    private fun retryPhotoUpload() {
        viewModelScope.launch { commitPhoto() }
    }

    private fun skipPhotoAndContinue() {
        FiLog.w("ViewModel", "Photo skipped — notifying server with empty filename")
        wsManager.sendJson(JSONObject().apply {
            put("type",        "photo_taken")
            put("photo_index", reviewPhotoIndex)
            put("filename",    "")
        })
    }

    private suspend fun commitPhoto() {
        val file = reviewPhotoFile ?: return
        _uiState.value = UiState.UploadingPhoto(reviewPhotoIndex)
        try {
            val capture = PhotoCapture(reviewPhotoPrompt, reviewPhotoIsSelfie, file, pendingPhotoGeo)
            repo.uploadPhoto(caseId, capture)
            collectedPhotos += capture
            pendingPhotoGeo = null
            FiLog.i("ViewModel", "Photo uploaded [${collectedPhotos.size}]: ${file.name}")
            // Notify server so it advances the session
            wsManager.sendJson(JSONObject().apply {
                put("type",        "photo_taken")
                put("photo_index", reviewPhotoIndex)
                put("filename",    file.name)
            })
        } catch (e: Exception) {
            FiLog.e("ViewModel", "Photo upload failed", e)
            _uiState.value = UiState.Error(
                message   = "Photo upload failed: ${e.message}\n\nSave to retry, Discard to skip.",
                showRetry = true
            )
        }
    }

    // ── Submit: recording + session metadata (photos already on server) ────────

    fun submitSession() {
        viewModelScope.launch {
            FiLog.i("ViewModel", "Submit: case=$caseId rec=${recordingFile?.name}")
            _uiState.value = UiState.Uploading
            try {
                val session = FiSession(
                    sessionId     = caseId,
                    deviceId      = deviceId,
                    startedAt     = startedAt,
                    endedAt       = iso.format(Date()),
                    answers       = collectedAnswers.toList(),
                    photos        = collectedPhotos.toList(),
                    recordingFile = recordingFile
                )
                val resp = repo.submitSession(session)
                FiLog.i("ViewModel", "Submit success: ${resp.message}")
                _uiState.value = UiState.Done("Case $caseId submitted.\n${resp.message}")
            } catch (e: Exception) {
                FiLog.e("ViewModel", "Submit failed", e)
                _uiState.value = UiState.Error("Submit failed: ${e.message}")
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        audioRecorder.stop()
        audioPlayer.release()
        tts?.stop()
        tts?.shutdown()
    }
}
