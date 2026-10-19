package com.quakemesh.app

import android.content.Context

enum class AlertKind { AUTHORITATIVE_PHYSICAL, AUTHORITATIVE_SIMULATION, CONTROLLED_TEST, LEGACY }

data class AlertPresentation(
    val kind: AlertKind,
    val channelId: String,
    val provenanceLabel: String,
    val headsUp: Boolean,
    val requestFullScreen: Boolean,
    val canAcknowledge: Boolean,
)

object AlertPresentationPolicy {
    fun classify(alert: AlertRecord): AlertKind = when {
        alert.controlledTest || alert.status.equals("CONTROLLED_TEST", true) -> AlertKind.CONTROLLED_TEST
        !alert.authoritativeRecord || alert.alertId.startsWith("legacy:") -> AlertKind.LEGACY
        alert.provenanceType.equals("scenario", true) || alert.provenanceType.equals("simulation", true) -> AlertKind.AUTHORITATIVE_SIMULATION
        else -> AlertKind.AUTHORITATIVE_PHYSICAL
    }

    fun forAlert(alert: AlertRecord): AlertPresentation {
        val kind = classify(alert)
        return AlertPresentation(
            kind = kind,
            channelId = if (kind == AlertKind.CONTROLLED_TEST) NotificationHelper.DEMO_CHANNEL else NotificationHelper.ALERT_CHANNEL,
            provenanceLabel = when (kind) {
                AlertKind.AUTHORITATIVE_PHYSICAL -> "Physical-device evidence · cloud corroborated"
                AlertKind.AUTHORITATIVE_SIMULATION -> "Synthetic scenario evidence · cloud corroborated"
                AlertKind.CONTROLLED_TEST -> "LOCAL CONTROLLED PREVIEW · no earthquake claim"
                AlertKind.LEGACY -> "Legacy message · authority not established"
            },
            headsUp = true,
            // QuakeMesh is not an alarm-clock or calling app. Android and user
            // settings remain authoritative; heads-up is the compliant fallback.
            requestFullScreen = false,
            canAcknowledge = alert.authoritativeRecord && !alert.controlledTest && !alert.alertId.startsWith("legacy:"),
        )
    }
}

object AlertDeliveryKey {
    fun forMessage(alertId: String, eventId: String): String =
        if (alertId.isNotBlank()) "alert:$alertId" else "legacy-event:$eventId"
}

object AlertDeliveryDeduplicator {
    private const val PREFS = "quakemesh_alert_dedupe"

    fun firstDelivery(context: Context, alertId: String, eventId: String): Boolean {
        val key = AlertDeliveryKey.forMessage(alertId, eventId)
        val preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (preferences.getBoolean(key, false)) return false
        preferences.edit().putBoolean(key, true).apply()
        return true
    }
}

object NotificationPermissionPolicy {
    fun requiresRuntimePermission(sdkInt: Int): Boolean = sdkInt >= 33
}
