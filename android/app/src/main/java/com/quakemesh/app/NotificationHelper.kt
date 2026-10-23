package com.quakemesh.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.media.AudioAttributes
import android.net.Uri
import android.os.Build

object NotificationHelper {
    const val ALERT_CHANNEL = "quakemesh_warnings_v3"
    const val DEMO_CHANNEL = "quakemesh_controlled_demo_v1"
    const val MONITOR_CHANNEL = "quakemesh_monitoring_v1"

    private fun sound(context: Context, resource: Int): Uri =
        Uri.parse("android.resource://${context.packageName}/$resource")

    fun ensureChannels(context: Context) {
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val alarmAudio = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).build()
        manager.createNotificationChannel(NotificationChannel(MONITOR_CHANNEL, "QuakeMesh monitoring", NotificationManager.IMPORTANCE_LOW).apply {
            description = "Silent foreground sensor monitoring"
            setSound(null, null)
            enableVibration(false)
        })
        manager.createNotificationChannel(NotificationChannel(ALERT_CHANNEL, "QuakeMesh corroborated warnings", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Authoritative corroborated QuakeMesh warning records"
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 700, 250, 700, 250, 1000)
            setSound(sound(context, R.raw.quakemesh_warning_v1), alarmAudio)
            lightColor = Color.RED
            enableLights(true)
            if (manager.isNotificationPolicyAccessGranted) setBypassDnd(true)
        })
        manager.createNotificationChannel(NotificationChannel(DEMO_CHANNEL, "QuakeMesh controlled previews", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Local, explicitly labeled demonstration previews"
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 180, 120, 180)
            setSound(sound(context, R.raw.quakemesh_demo_v1), alarmAudio)
            lightColor = Color.rgb(245, 145, 40)
            enableLights(true)
        })
    }

    fun ensureChannel(context: Context) = ensureChannels(context)

    fun monitoring(context: Context): Notification {
        ensureChannels(context)
        return Notification.Builder(context, MONITOR_CHANNEL)
            .setSmallIcon(android.R.drawable.ic_menu_compass)
            .setContentTitle("QuakeMesh monitoring")
            .setContentText("Accelerometer and location trigger detection active")
            .setOngoing(true)
            .build()
    }

    private fun warningNotification(context: Context, title: String, body: String, alert: AlertRecord, channelOverride: String? = null): Notification {
        ensureChannels(context)
        val presentation = AlertPresentationPolicy.forAlert(alert)
        val pending = PendingIntent.getActivity(
            context,
            alert.alertId.hashCode(),
            WarningActivity.intent(context, alert, title, body),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val detail = "$body\n${presentation.provenanceLabel}\nEvent: ${alert.eventId}\nAlert: ${alert.alertId}"
        val stop = PendingIntent.getService(
            context, alert.alertId.hashCode() xor 0x5A5A,
            Intent(context, AlertAttentionService::class.java).setAction(AlertAttentionService.ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val builder = Notification.Builder(context, channelOverride ?: presentation.channelId)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle(title)
            .setContentText(body)
            .setSubText(presentation.provenanceLabel)
            .setStyle(Notification.BigTextStyle().bigText(detail))
            .setCategory(Notification.CATEGORY_ALARM)
            .setPriority(Notification.PRIORITY_MAX)
            .setVisibility(Notification.VISIBILITY_PUBLIC)
            .setAutoCancel(true)
            .setContentIntent(pending)
            .addAction(Notification.Action.Builder(null, "STOP ALERT", stop).build())
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val fullScreenAllowed = Build.VERSION.SDK_INT < 34 || manager.canUseFullScreenIntent()
        if (presentation.requestFullScreen && fullScreenAllowed) builder.setFullScreenIntent(pending, true)
        return builder.build()
    }

    fun warning(context: Context, title: String, body: String, alert: AlertRecord): Notification =
        warningNotification(context, title, body, alert)

    fun showControlledPreview(context: Context) {
        showControlledPreview(context, "local-preview-${System.currentTimeMillis()}", false)
    }

    fun showControlledPreview(context: Context, previewId: String, useWarningTone: Boolean) {
        val now = System.currentTimeMillis()
        val alert = AlertRecord(
            alertId = previewId, eventId = "LOCAL-PREVIEW", eventVersion = 1,
            status = "CONTROLLED_TEST", deviceId = DeviceIdentity.id(context), createdAtMs = now,
            acknowledgedAtMs = null, acknowledgementSource = null, provenanceType = "local-test",
            authoritativeRecord = false, controlledTest = true,
        )
        val toneLabel = if (useWarningTone) "warning-channel tone" else "demonstration-channel tone"
        val notification = warningNotification(
            context,
            "CONTROLLED TEST — NOT AN EARTHQUAKE ALERT",
            "Local $toneLabel delivery check. This is not an earthquake warning.",
            alert,
            if (useWarningTone) ALERT_CHANNEL else DEMO_CHANNEL,
        )
        (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
            .notify(alert.alertId.hashCode(), notification)
    }
}
