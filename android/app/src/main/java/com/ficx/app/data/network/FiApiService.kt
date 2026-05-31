package com.ficx.app.data.network

import com.ficx.app.data.model.PhotoUploadResponse
import com.ficx.app.data.model.UploadResponse
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path

interface FiApiService {

    /** Upload a single photo immediately after the field officer saves it. */
    @Multipart
    @POST("api/fi-session/{caseId}/photo")
    suspend fun uploadPhoto(
        @Path("caseId") caseId: String,
        @Part photo: MultipartBody.Part,
        @Part("meta_json") metaJson: RequestBody
    ): PhotoUploadResponse

    /** Final submit: recording file + session metadata (answers, timestamps). */
    @Multipart
    @POST("api/fi-session/{caseId}/submit")
    suspend fun submitSession(
        @Path("caseId") caseId: String,
        @Part("metadata_json") metadataJson: RequestBody,
        @Part recording: MultipartBody.Part?
    ): UploadResponse
}
