package com.quakemesh.app

import android.app.Activity
import android.app.NotificationManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Debug-only ADB entry point for labeled, local, non-authoritative notification QA. */
class LocalNotificationPreviewReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.getBooleanExtra("clear_package_notifications", false)) {
            (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancelAll()
            resultCode = Activity.RESULT_OK
            resultData = "package-notifications-cleared"
            return
        }
        val previewId = intent.getStringExtra("preview_id") ?: "adb-controlled-preview"
        val tone = intent.getStringExtra("tone") ?: "demo"
        if (!AlertDeliveryDeduplicator.firstDelivery(context, previewId, "LOCAL-PREVIEW")) {
            resultCode = Activity.RESULT_CANCELED
            resultData = "duplicate-suppressed"
            return
        }
        NotificationHelper.showControlledPreview(context, previewId, tone == "warning")
        resultCode = Activity.RESULT_OK
        resultData = "posted-controlled-$tone-preview"
    }
}
