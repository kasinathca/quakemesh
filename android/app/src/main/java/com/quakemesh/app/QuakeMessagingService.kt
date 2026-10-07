package com.quakemesh.app

import android.app.NotificationManager
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

class QuakeMessagingService : FirebaseMessagingService() {
    private fun firstDelivery(alertId: String, eventId: String): Boolean {
        val prefs = getSharedPreferences("quakemesh_alert_dedupe", MODE_PRIVATE)
        val key = if (alertId.isNotBlank()) "alert:$alertId" else "legacy-event:$eventId"
        if (prefs.getBoolean(key, false)) return false
        prefs.edit().putBoolean(key, true).apply()
        return true
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val alertId = message.data["alert_id"].orEmpty()
        val eventId = message.data["event_id"].orEmpty()
        if (eventId.isBlank() || !firstDelivery(alertId, eventId)) return
        val alert = AlertRecord(
            alertId = alertId.ifBlank { "legacy:$eventId" },
            eventId = eventId,
            eventVersion = message.data["event_version"]?.toIntOrNull() ?: 1,
            status = message.data["status"] ?: "TARGETED",
            deviceId = message.data["device_id"],
            createdAtMs = message.data["created_at_ms"]?.toLongOrNull()
                ?: message.data["received_at_ms"]?.toLongOrNull()
                ?: System.currentTimeMillis(),
            acknowledgedAtMs = null,
            acknowledgementSource = null,
        )
        MonitoringState.recordAlert(this, alert)
        val title = message.notification?.title ?: "QuakeMesh corroborated event"
        val body = message.notification?.body
            ?: "Experimental ground-motion evidence was corroborated across distinct locations."
        val notification = NotificationHelper.warning(this, title, body, alert)
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager)
            .notify(alert.alertId.hashCode(), notification)
    }

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        // The next scheduled heartbeat registers the current token without logging it.
    }
}
