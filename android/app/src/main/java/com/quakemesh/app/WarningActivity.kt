package com.quakemesh.app

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import java.text.DateFormat
import java.util.Date

class WarningActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val alert = fromIntent(intent)
        val presentation = AlertPresentationPolicy.forAlert(alert)
        if (alert.controlledTest && !alert.testMessageId.isNullOrBlank() && !alert.deviceId.isNullOrBlank()) {
            ApiClient.controlledTestReceipt(alert.testMessageId, alert.deviceId, "OPENED")
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(24), dp(28), dp(24), dp(32))
            setBackgroundColor(if (presentation.kind == AlertKind.CONTROLLED_TEST) Color.rgb(255, 247, 229) else Color.rgb(255, 240, 238))
        }
        root.addView(TextView(this).apply {
            text = if (presentation.kind == AlertKind.CONTROLLED_TEST) "CONTROLLED NOTIFICATION PREVIEW" else "QUAKEMESH WARNING"
            textSize = 13f; letterSpacing = .08f; typeface = Typeface.DEFAULT_BOLD
            setTextColor(if (presentation.kind == AlertKind.CONTROLLED_TEST) Color.rgb(139, 82, 0) else Color.rgb(154, 38, 34))
        })
        root.addView(TextView(this).apply {
            text = intent.getStringExtra(EXTRA_TITLE) ?: "QuakeMesh event"
            textSize = 27f; typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
            setTextColor(Color.rgb(25, 34, 43)); setPadding(0, dp(10), 0, dp(8))
        })
        root.addView(TextView(this).apply {
            text = intent.getStringExtra(EXTRA_BODY).orEmpty(); textSize = 16f
            setTextColor(Color.rgb(45, 56, 67)); setPadding(0, 0, 0, dp(20))
        })
        listOf(
            "Status" to alert.status,
            "Provenance" to presentation.provenanceLabel,
            "H3 warning area" to alert.warningAreaH3.ifEmpty { listOf("Not supplied") }.joinToString("\n"),
            "Event identity" to alert.eventId,
            "Alert identity" to alert.alertId,
            "Timestamp" to DateFormat.getDateTimeInstance().format(Date(alert.createdAtMs)),
            "Acknowledgement" to if (presentation.canAcknowledge) "Available from event details" else "Not available for this preview/message",
        ).forEach { (label, value) ->
            root.addView(TextView(this).apply { text = label; textSize = 11f; setTextColor(Color.DKGRAY); setPadding(0, dp(10), 0, 2) })
            root.addView(TextView(this).apply { text = value; textSize = 15f; setTextColor(Color.rgb(24, 34, 44)) })
        }
        root.addView(Button(this).apply {
            text = "View details"; isAllCaps = false; gravity = Gravity.CENTER
            setOnClickListener { startActivity(Intent(this@WarningActivity, MainActivity::class.java).putExtra("alert_id", alert.alertId)); finish() }
        }, marginTop(dp(24)))
        root.addView(Button(this).apply { text = "Dismiss"; isAllCaps = false; setOnClickListener { finish() } }, marginTop(dp(8)))
        setContentView(ScrollView(this).apply { addView(root) })
    }

    private fun fromIntent(intent: Intent) = AlertRecord(
        alertId = intent.getStringExtra(EXTRA_ALERT_ID).orEmpty(), eventId = intent.getStringExtra(EXTRA_EVENT_ID).orEmpty(),
        eventVersion = intent.getIntExtra(EXTRA_EVENT_VERSION, 1), status = intent.getStringExtra(EXTRA_STATUS) ?: "TARGETED",
        deviceId = intent.getStringExtra(EXTRA_DEVICE_ID), createdAtMs = intent.getLongExtra(EXTRA_CREATED_AT, System.currentTimeMillis()),
        acknowledgedAtMs = null, acknowledgementSource = null, provenanceType = intent.getStringExtra(EXTRA_PROVENANCE),
        warningAreaH3 = intent.getStringArrayListExtra(EXTRA_WARNING_AREA).orEmpty(),
        authoritativeRecord = intent.getBooleanExtra(EXTRA_AUTHORITATIVE, true), controlledTest = intent.getBooleanExtra(EXTRA_CONTROLLED, false),
        testMessageId = intent.getStringExtra(EXTRA_TEST_MESSAGE_ID),
    )

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
    private fun marginTop(value: Int) = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { topMargin = value }

    companion object {
        const val EXTRA_ALERT_ID = "warning_alert_id"; const val EXTRA_EVENT_ID = "warning_event_id"; const val EXTRA_EVENT_VERSION = "warning_event_version"
        const val EXTRA_STATUS = "warning_status"; const val EXTRA_DEVICE_ID = "warning_device_id"; const val EXTRA_CREATED_AT = "warning_created_at"
        const val EXTRA_PROVENANCE = "warning_provenance"; const val EXTRA_WARNING_AREA = "warning_area_h3"; const val EXTRA_AUTHORITATIVE = "warning_authoritative"
        const val EXTRA_CONTROLLED = "warning_controlled"; const val EXTRA_TITLE = "warning_title"; const val EXTRA_BODY = "warning_body"
        const val EXTRA_TEST_MESSAGE_ID = "warning_test_message_id"

        fun intent(context: Context, alert: AlertRecord, title: String, body: String) = Intent(context, WarningActivity::class.java)
            .putExtra(EXTRA_ALERT_ID, alert.alertId).putExtra(EXTRA_EVENT_ID, alert.eventId).putExtra(EXTRA_EVENT_VERSION, alert.eventVersion)
            .putExtra(EXTRA_STATUS, alert.status).putExtra(EXTRA_DEVICE_ID, alert.deviceId).putExtra(EXTRA_CREATED_AT, alert.createdAtMs)
            .putExtra(EXTRA_PROVENANCE, alert.provenanceType).putStringArrayListExtra(EXTRA_WARNING_AREA, ArrayList(alert.warningAreaH3))
            .putExtra(EXTRA_AUTHORITATIVE, alert.authoritativeRecord).putExtra(EXTRA_CONTROLLED, alert.controlledTest)
            .putExtra(EXTRA_TEST_MESSAGE_ID, alert.testMessageId)
            .putExtra(EXTRA_TITLE, title).putExtra(EXTRA_BODY, body)
    }
}
