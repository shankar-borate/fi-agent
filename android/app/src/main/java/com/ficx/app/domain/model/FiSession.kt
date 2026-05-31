package com.ficx.app.domain.model

import java.io.File

data class FiSession(
    val sessionId: String,
    val deviceId: String,
    val startedAt: String,
    val endedAt: String = "",
    val answers: List<QuestionAnswer> = emptyList(),
    val photos: List<PhotoCapture> = emptyList(),
    val recordingFile: File? = null
)
