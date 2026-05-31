package com.ficx.app.domain.model

data class QuestionAnswer(
    val question: String,
    val answer: String,
    val geo: GeoPoint?
)
