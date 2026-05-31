package com.ficx.app.domain.usecase

import com.ficx.app.config.FiConfig
import com.ficx.app.domain.model.SessionStep

class BuildSessionStepsUseCase {

    fun execute(config: FiConfig): List<SessionStep> {
        val steps = mutableListOf<SessionStep>()

        // Q&A phase
        config.questions.forEachIndexed { i, q ->
            steps += SessionStep.AskQuestion(i, q)
            steps += SessionStep.ListenAnswer(i)
        }

        // Self photo phase
        steps += SessionStep.AnnouncePhoto(config.selfPhotoPrompt, isSelfie = true)
        steps += SessionStep.Countdown(config.countdownSeconds)
        steps += SessionStep.CapturePhoto(config.selfPhotoPrompt, isSelfie = true, index = 0)

        // Room photo phase — back camera
        config.photoPrompts.forEachIndexed { i, prompt ->
            steps += SessionStep.AnnouncePhoto(prompt, isSelfie = false)
            steps += SessionStep.Countdown(config.countdownSeconds)
            steps += SessionStep.CapturePhoto(prompt, isSelfie = false, index = i)
        }

        steps += SessionStep.Upload
        steps += SessionStep.Done
        return steps
    }
}
