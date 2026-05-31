package com.ficx.app.domain.model

import java.io.File

data class PhotoCapture(
    val prompt: String,
    val isSelfie: Boolean,
    val file: File,
    val geo: GeoPoint?
)
