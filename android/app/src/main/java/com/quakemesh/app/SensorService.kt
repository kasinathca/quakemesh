package com.quakemesh.app

import android.Manifest
import android.app.Service
import android.content.Intent
import android.content.pm.PackageManager
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import com.google.firebase.messaging.FirebaseMessaging
import kotlin.math.abs
import kotlin.math.sqrt

class SensorService : Service(), SensorEventListener, LocationListener {
    private lateinit var sensorManager: SensorManager
    private lateinit var locationManager: LocationManager
    private val handler = Handler(Looper.getMainLooper())
    private val deviations = ArrayDeque<Double>()
    private var lastLocation: Location? = null
    private var lastTriggerAt = 0L
    private val gravity = 9.80665
    private val rmsThreshold = .75
    private val peakThreshold = 1.80
    private val windowSize = 100
    private val triggerCooldownMs = 8_000L
    private val heartbeatIntervalMs = 30_000L
    private val heartbeatTask = object : Runnable {
        override fun run() {
            sendHeartbeat()
            handler.postDelayed(this, heartbeatIntervalMs)
        }
    }

    override fun onCreate() {
        super.onCreate()
        NotificationHelper.ensureChannel(this)
        startForeground(7001, NotificationHelper.monitoring(this))
        sensorManager = getSystemService(SENSOR_SERVICE) as SensorManager
        locationManager = getSystemService(LOCATION_SERVICE) as LocationManager
        val accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        if (accelerometer != null) {
            sensorManager.registerListener(this, accelerometer, SensorManager.SENSOR_DELAY_GAME)
        }
        MonitoringState.update(this) {
            it.copy(monitoring = true, sensorAvailable = accelerometer != null, apiFailure = null)
        }
        startLocationUpdates()
        handler.post(heartbeatTask)
    }

    private fun startLocationUpdates() {
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            MonitoringState.update(this) { it.copy(locationState = "Permission required") }
            return
        }
        try {
            locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 2_000, 1f, this)
            lastLocation = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER)
                ?: locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
            MonitoringState.update(this) {
                it.copy(locationState = if (lastLocation == null) "Acquiring location" else "Location available")
            }
        } catch (_: SecurityException) {
            MonitoringState.update(this) { it.copy(locationState = "Permission required") }
        } catch (_: Exception) {
            MonitoringState.update(this) { it.copy(locationState = "Location unavailable") }
        }
    }

    override fun onDestroy() {
        handler.removeCallbacks(heartbeatTask)
        sensorManager.unregisterListener(this)
        try { locationManager.removeUpdates(this) } catch (_: Exception) { }
        MonitoringState.update(this) { it.copy(monitoring = false) }
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit

    override fun onLocationChanged(location: Location) {
        lastLocation = location
        MonitoringState.update(this) { it.copy(locationState = "Location available") }
    }

    @Deprecated("legacy callbacks")
    override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) = Unit
    override fun onProviderEnabled(provider: String) = Unit
    override fun onProviderDisabled(provider: String) {
        MonitoringState.update(this) { it.copy(locationState = "Location provider disabled") }
    }

    override fun onSensorChanged(event: SensorEvent) {
        val x = event.values[0].toDouble()
        val y = event.values[1].toDouble()
        val z = event.values[2].toDouble()
        val deviation = abs(sqrt(x * x + y * y + z * z) - gravity)
        deviations.addLast(deviation)
        while (deviations.size > windowSize) deviations.removeFirst()
        if (deviations.size < windowSize) return
        val rms = sqrt(deviations.sumOf { it * it } / deviations.size)
        val peak = deviations.maxOrNull() ?: 0.0
        val now = System.currentTimeMillis()
        if (rms >= rmsThreshold && peak >= peakThreshold && now - lastTriggerAt >= triggerCooldownMs) {
            val location = lastLocation ?: return
            lastTriggerAt = now
            MonitoringState.update(this) {
                it.copy(localMotionAtMs = now, localMotionRms = rms, localMotionPeak = peak)
            }
            ApiClient.trigger(
                DeviceIdentity.id(this),
                DeviceIdentity.nextSeq(this),
                location.latitude,
                location.longitude,
                rms,
                peak,
            ) { result -> updateApiState(result, false) }
        }
    }

    private fun sendHeartbeat() {
        val location = lastLocation ?: return
        if (!BuildConfig.QUAKEMESH_FIREBASE_ENABLED) {
            submitHeartbeat(location, null)
            return
        }
        FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
            submitHeartbeat(location, if (task.isSuccessful) task.result else null)
        }
    }

    private fun submitHeartbeat(location: Location, token: String?) {
        ApiClient.heartbeat(
            DeviceIdentity.id(this),
            DeviceIdentity.nextSeq(this),
            location.latitude,
            location.longitude,
            token,
        ) { result -> updateApiState(result, true) }
    }

    private fun updateApiState(result: ApiResult<ObservationReceipt>, heartbeat: Boolean) {
        when (result) {
            is ApiResult.Success -> MonitoringState.update(this) {
                it.copy(
                    latestHeartbeatAtMs = if (heartbeat) System.currentTimeMillis() else it.latestHeartbeatAtMs,
                    latestHeartbeatRequestId = if (heartbeat) result.requestId else it.latestHeartbeatRequestId,
                    apiFailure = null,
                )
            }
            is ApiResult.Failure -> MonitoringState.update(this) { it.copy(apiFailure = result.error) }
        }
    }
}
