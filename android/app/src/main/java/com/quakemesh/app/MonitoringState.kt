package com.quakemesh.app

import android.content.Context
import android.content.Intent
import org.json.JSONObject

data class MonitoringSnapshot(
    val monitoring: Boolean = false,
    val sensorAvailable: Boolean = true,
    val locationState: String = "Waiting for location",
    val latestHeartbeatAtMs: Long? = null,
    val latestHeartbeatRequestId: String? = null,
    val localMotionAtMs: Long? = null,
    val localMotionRms: Double? = null,
    val localMotionPeak: Double? = null,
    val apiFailure: ApiFailure? = null,
    val latestAlert: AlertRecord? = null,
)

object MonitoringState {
    const val ACTION_CHANGED = "com.quakemesh.app.MONITORING_STATE_CHANGED"
    private const val PREFS = "quakemesh_state"
    private const val ALERT = "latest_alert"
    private val lock = Any()
    private var current = MonitoringSnapshot()

    fun snapshot(context: Context): MonitoringSnapshot = synchronized(lock) {
        if (current.latestAlert == null) {
            current = current.copy(latestAlert = loadAlert(context))
        }
        current
    }

    fun update(context: Context, transform: (MonitoringSnapshot) -> MonitoringSnapshot) {
        synchronized(lock) { current = transform(snapshot(context)) }
        context.sendBroadcast(Intent(ACTION_CHANGED).setPackage(context.packageName))
    }

    fun recordAlert(context: Context, alert: AlertRecord) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(ALERT, JSONObject()
                .put("alert_id", alert.alertId)
                .put("event_id", alert.eventId)
                .put("event_version", alert.eventVersion)
                .put("status", alert.status)
                .put("device_id", alert.deviceId)
                .put("created_at_ms", alert.createdAtMs)
                .put("acknowledged_at_ms", alert.acknowledgedAtMs)
                .put("acknowledgement_source", alert.acknowledgementSource)
                .toString())
            .apply()
        update(context) { it.copy(latestAlert = alert) }
    }

    private fun loadAlert(context: Context): AlertRecord? {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(ALERT, null)
            ?: return null
        return try { ApiJson.alert(JSONObject(raw)) } catch (_: Exception) { null }
    }
}
