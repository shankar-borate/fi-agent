package com.ficx.app.data.network

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object FiApiClient {

    private var retrofit: Retrofit? = null
    private var currentBaseUrl: String = ""

    fun getService(baseUrl: String, timeoutSec: Long = 120L): FiApiService {
        val normalised = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        if (retrofit == null || currentBaseUrl != normalised) {
            currentBaseUrl = normalised
            retrofit = buildRetrofit(normalised, timeoutSec)
        }
        return retrofit!!.create(FiApiService::class.java)
    }

    private fun buildRetrofit(baseUrl: String, timeoutSec: Long): Retrofit {
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.HEADERS
        }
        val client = OkHttpClient.Builder()
            .addInterceptor(logging)
            .connectTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(timeoutSec, TimeUnit.SECONDS)
            .readTimeout(timeoutSec, TimeUnit.SECONDS)
            .build()

        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }
}
