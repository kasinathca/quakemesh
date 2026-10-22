package com.quakemesh.app

import android.app.NotificationManager
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

class QuakeMessagingService : FirebaseMessagingService() {
    private fun firstDelivery(alertId: String, eventId: String): Boolean {
        return AlertDeliveryDeduplicator.firstDelivery(this, alertId, eventId)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val alertId = message.data["alert_id"].orEmpty()
        val eventId = message.data["event_id"].orEmpty()
        if (eventId.isBlank() || !firstDelivery(alertId, eventId)) return
        val controlledTest = message.data["controlled_test"].toBoolean()
        val testMessageId = message.data["test_message_id"]
        val deviceId = message.data["device_id"]
        if (controlledTest && !testMessageId.isNullOrBlank() && !deviceId.isNullOrBlank()) {
            ApiClient.controlledTestReceipt(testMessageId, deviceId, "FCM_RECEIVED")
        }
        val alert = AlertRecord(
            alertId = alertId.ifBlank { "legacy:$eventId" },
            eventId = eventId,
            eventVersion = message.data["event_version"]?.toIntOrNull() ?: 1,
            status = message.data["status"] ?: "TARGETED",
            deviceId = deviceId,
            createdAtMs = message.data["created_at_ms"]?.toLongOrNull()
                ?: message.data["received_at_ms"]?.toLongOrNull()
                ?: System.currentTimeMillis(),
            acknowledgedAtMs = null,
            acknowledgementSource = null,
            provenanceType = message.data["provenance_type"],
            warningAreaH3 = message.data["warning_area_h3"]?.split(',')?.filter { it.isNotBlank() } ?: emptyList(),
            authoritativeRecord = message.data["authoritative_record"]?.toBooleanStrictOrNull()
                ?: (alertId.isNotBlank() && !controlledTest),
            controlledTest = controlledTest,
            testMessageId = testMessageId,
        )
        MonitoringState.recordAlert(this, alert)
        val title = message.data["title"] ?: message.notification?.title ?: "QuakeMesh corroborated event"
        val body = message.data["body"] ?: message.notification?.body
            ?: "Experimental ground-motion evidence was corroborated across distinct locations."
        val notification = NotificationHelper.warning(this, title, body, alert)
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager)
            .notify(alert.alertId.hashCode(), notification)
        if (controlledTest && !testMessageId.isNullOrBlank() && !deviceId.isNullOrBlank()) {
            ApiClient.controlledTestReceipt(testMessageId, deviceId, "NOTIFICATION_POSTED")
        }
    }

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        // The next scheduled heartbeat registers the current token without logging it.
    }
}
