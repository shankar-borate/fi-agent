package com.ficx.app.config

/**
 * Central configuration — edit lists here or load from remote config.
 */
data class FiConfig(
    val serverUrl: String = "http://3.7.0.169:8000",
    val questions: List<String> = listOf(
        "What is your name?",
        "What is your date of birth?",
        "What is the address of your pincode?"
    ),
    val selfPhotoPrompt: String = "I am taking your photo now. Please look at the camera.",
    val photoPrompts: List<String> = listOf(
        "I will now take a photo of the hall. Please show the hall.",
        "I will now take a photo of the kitchen. Please show the kitchen.",
        "I will now take a photo of the bedroom. Please show the bedroom.",
        "I will now take a photo outside. Please show outside."
    ),
    val countdownSeconds: Int = 10,
    val sttTimeoutMs: Long = 5_000L,
    val uploadTimeoutSec: Long = 120L
) {
    companion object {
        val DEFAULT = FiConfig()
    }
}
