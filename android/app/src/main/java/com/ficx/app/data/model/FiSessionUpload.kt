package com.ficx.app.data.model

import com.google.gson.annotations.SerializedName

data class GeoPointDto(
    @SerializedName("latitude")  val latitude: Double,
    @SerializedName("longitude") val longitude: Double,
    @SerializedName("timestamp") val timestamp: String
)

data class QuestionAnswerDto(
    @SerializedName("question") val question: String,
    @SerializedName("answer")   val answer: String,
    @SerializedName("geo")      val geo: GeoPointDto?
)

data class PhotoMetaDto(
    @SerializedName("prompt")   val prompt: String,
    @SerializedName("filename") val filename: String,
    @SerializedName("geo")      val geo: GeoPointDto?
)

data class SessionMetadataDto(
    @SerializedName("session_id")          val sessionId: String,
    @SerializedName("device_id")           val deviceId: String,
    @SerializedName("started_at")          val startedAt: String,
    @SerializedName("ended_at")            val endedAt: String,
    @SerializedName("questions")           val questions: List<QuestionAnswerDto>,
    @SerializedName("photos")              val photos: List<PhotoMetaDto>,
    @SerializedName("recording_filename")  val recordingFilename: String?
)

data class PhotoUploadResponse(
    @SerializedName("status")   val status: String,
    @SerializedName("filename") val filename: String
)

data class UploadResponse(
    @SerializedName("session_id")     val sessionId: String,
    @SerializedName("status")         val status: String,
    @SerializedName("session_folder") val sessionFolder: String,
    @SerializedName("files_saved")    val filesSaved: List<String>,
    @SerializedName("message")        val message: String
)
