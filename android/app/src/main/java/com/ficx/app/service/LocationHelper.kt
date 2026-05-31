package com.ficx.app.service

import android.annotation.SuppressLint
import android.content.Context
import android.os.Looper
import com.ficx.app.domain.model.GeoPoint
import com.google.android.gms.location.*
import kotlinx.coroutines.suspendCancellableCoroutine
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.coroutines.resume

class LocationHelper(context: Context) {

    private val client: FusedLocationProviderClient =
        LocationServices.getFusedLocationProviderClient(context)

    private val iso = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)

    @SuppressLint("MissingPermission")
    suspend fun getLocation(): GeoPoint? = suspendCancellableCoroutine { cont ->
        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 1000)
            .setMaxUpdates(1)
            .build()

        val callback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                client.removeLocationUpdates(this)
                val loc = result.lastLocation
                val gp = loc?.let {
                    GeoPoint(it.latitude, it.longitude, iso.format(Date(it.time)))
                }
                if (cont.isActive) cont.resume(gp)
            }
        }

        client.requestLocationUpdates(request, callback, Looper.getMainLooper())
        cont.invokeOnCancellation { client.removeLocationUpdates(callback) }
    }
}
