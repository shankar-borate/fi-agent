package com.ficx.app.domain.model

sealed class SessionStep {
    data class AskQuestion(val index: Int, val text: String) : SessionStep()
    data class ListenAnswer(val questionIndex: Int) : SessionStep()
    data class AnnouncePhoto(val prompt: String, val isSelfie: Boolean) : SessionStep()
    data class Countdown(val seconds: Int) : SessionStep()
    data class CapturePhoto(val prompt: String, val isSelfie: Boolean, val index: Int) : SessionStep()
    object Upload : SessionStep()
    object Done : SessionStep()
}
