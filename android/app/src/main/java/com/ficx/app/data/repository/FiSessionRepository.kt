package com.ficx.app.data.repository

import com.ficx.app.config.FiConfig
import com.ficx.app.data.model.*
import com.ficx.app.data.network.FiApiClient
import com.ficx.app.domain.model.FiSession
import com.ficx.app.domain.model.PhotoCapture
import com.google.gson.Gson
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

class FiSessionRepository(private val config: FiConfig) {

    private val gson = Gson()

    /** Upload a single photo immediately after the field officer taps Save. */
    suspend fun uploadPhoto(caseId: String, capture: PhotoCapture): PhotoUploadResponse {
        val service = FiApiClient.getService(config.serverUrl, 60L)

        val bytes = try {
            capture.file.readBytes()
        } catch (e: Exception) {
            throw Exception("Cannot read photo '${capture.file.name}': ${e.message}")
        }

        val photoPart = MultipartBody.Part.createFormData(
            "photo", capture.file.name,
            bytes.toRequestBody("image/jpeg".toMediaType())
        )

        val metaBody = gson.toJson(
            mapOf(
                "prompt"    to capture.prompt,
                "is_selfie" to capture.isSelfie,
                "geo"       to capture.geo?.let {
                    mapOf("latitude" to it.latitude, "longitude" to it.longitude, "timestamp" to it.timestamp)
                }
            )
        ).toRequestBody("application/json".toMediaType())

        return service.uploadPhoto(caseId, photoPart, metaBody)
    }

    /** Final submit: uploads the recording + all Q&A metadata. Photos are already on the server. */
    suspend fun submitSession(session: FiSession): UploadResponse {
        val service = FiApiClient.getService(config.serverUrl, config.uploadTimeoutSec)

        val answerDtos = session.answers.map { qa ->
            QuestionAnswerDto(
                question = qa.question,
                answer   = qa.answer,
                geo      = qa.geo?.let { GeoPointDto(it.latitude, it.longitude, it.timestamp) }
            )
        }

        val metadata = SessionMetadataDto(
            sessionId         = session.sessionId,
            deviceId          = session.deviceId,
            startedAt         = session.startedAt,
            endedAt           = session.endedAt,
            questions         = answerDtos,
            photos            = emptyList(),  // already uploaded individually
            recordingFilename = session.recordingFile?.takeIf { it.exists() }?.name
        )

        val metaBody = gson.toJson(metadata).toRequestBody("application/json".toMediaType())

        val recordingPart = session.recordingFile?.takeIf { it.exists() }?.let { file ->
            try {
                val bytes = file.readBytes()
                MultipartBody.Part.createFormData(
                    "recording", file.name,
                    bytes.toRequestBody("video/mp4".toMediaType())
                )
            } catch (e: Exception) {
                throw Exception("Cannot read recording '${file.name}': ${e.message}")
            }
        }

        return service.submitSession(session.sessionId, metaBody, recordingPart)
    }
}
