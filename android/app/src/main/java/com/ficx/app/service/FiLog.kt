package com.ficx.app.service

import android.util.Log

/**
 * Thin logging wrapper — prefixes every tag with "FiAgent/" for easy logcat filtering.
 * Usage: FiLog.i("WS", "Connected")   →  tag = "FiAgent/WS"
 */
object FiLog {
    private const val ROOT = "FiAgent"

    fun v(tag: String, msg: String) = Log.v("$ROOT/$tag", msg)
    fun d(tag: String, msg: String) = Log.d("$ROOT/$tag", msg)
    fun i(tag: String, msg: String) = Log.i("$ROOT/$tag", msg)
    fun w(tag: String, msg: String) = Log.w("$ROOT/$tag", msg)
    fun e(tag: String, msg: String, t: Throwable? = null) =
        if (t != null) Log.e("$ROOT/$tag", msg, t) else Log.e("$ROOT/$tag", msg)
}
