package com.quakemesh.app

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import java.text.DateFormat
import java.util.Date

class WarningActivity : Activity() {
    private lateinit var alert: AlertRecord
    private val handler = Handler(Looper.getMainLooper())
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        alert = fromIntent(intent)
        val presentation = AlertPresentationPolicy.forAlert(alert)
        val testMessageId = alert.testMessageId
        val alertDeviceId = alert.deviceId
        if (alert.controlledTest && !testMessageId.isNullOrBlank() && !alertDeviceId.isNullOrBlank()) {
            ApiClient.controlledTestReceipt(testMessageId, alertDeviceId, "OPENED")
        }
        if (!alert.controlledTest && alertDeviceId != null) ApiClient.alertReceipt(alert.alertId, alertDeviceId, "OPENED")
        val emergency = presentation.kind == AlertKind.AUTHORITATIVE_SIMULATION || presentation.kind == AlertKind.AUTHORITATIVE_PHYSICAL
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(24), dp(28), dp(24), dp(32))
            setBackgroundColor(if (emergency) Color.rgb(91, 11, 11) else Color.rgb(255, 247, 229))
        }
        val beacon = TextView(this).apply {
            text = "●  QUAKEMESH  ●"
            textSize = 13f; letterSpacing = .08f; typeface = Typeface.DEFAULT_BOLD
            setTextColor(if (emergency) Color.rgb(255, 210, 210) else Color.rgb(139, 82, 0)); gravity = Gravity.CENTER
        }
        root.addView(beacon)
        if (emergency) beacon.animate().alpha(0.25f).setDuration(550).withEndAction { beacon.animate().alpha(1f).setDuration(550).start() }.start()
        root.addView(TextView(this).apply {
            text = if (presentation.kind == AlertKind.AUTHORITATIVE_SIMULATION) "SIMULATED\nEARTHQUAKE" else intent.getStringExtra(EXTRA_TITLE) ?: "QuakeMesh event"
            textSize = if (emergency) 38f else 27f; typeface = Typeface.create("sans-serif-black", Typeface.BOLD); gravity = Gravity.CENTER
            setTextColor(if (emergency) Color.WHITE else Color.rgb(25, 34, 43)); setPadding(0, dp(24), 0, dp(14))
        })
        root.addView(TextView(this).apply {
            text = intent.getStringExtra(EXTRA_BODY).orEmpty(); textSize = 18f; gravity = Gravity.CENTER
            setTextColor(if (emergency) Color.rgb(255, 230, 230) else Color.rgb(45, 56, 67)); setPadding(0, 0, 0, dp(20))
        })
        listOf(
            "Status" to alert.status,
            "Provenance" to presentation.provenanceLabel,
            "H3 warning area" to alert.warningAreaH3.ifEmpty { listOf("Not supplied") }.joinToString("\n"),
            "Event identity" to alert.eventId,
            "Alert identity" to alert.alertId,
            "Timestamp" to DateFormat.getDateTimeInstance().format(Date(alert.createdAtMs)),
            "Corroboration" to "${alert.corroboratingDevices ?: "—"} devices · ${alert.corroboratingCells ?: "—"} H3 cells",
            "Acknowledgement" to if (presentation.canAcknowledge) "Available from event details" else "Not available for this preview/message",
        ).forEach { (label, value) ->
            root.addView(TextView(this).apply { text = label; textSize = 11f; setTextColor(if (emergency) Color.rgb(255, 185, 185) else Color.DKGRAY); setPadding(0, dp(10), 0, 2) })
            root.addView(TextView(this).apply { text = value; textSize = 15f; setTextColor(if (emergency) Color.WHITE else Color.rgb(24, 34, 44)) })
        }
        root.addView(Button(this).apply {
            text = if (presentation.canAcknowledge) "ACKNOWLEDGE / DISMISS" else "VIEW DETAILS"; isAllCaps = false; gravity = Gravity.CENTER
            setOnClickListener {
                stopAttention()
                if (presentation.canAcknowledge && alertDeviceId != null) ApiClient.acknowledge(alert.alertId, alertDeviceId) { finish() }
                else { startActivity(Intent(this@WarningActivity, MainActivity::class.java).putExtra("alert_id", alert.alertId)); finish() }
            }
        }, marginTop(dp(24)))
        root.addView(Button(this).apply { text = "STOP ALERT SOUND"; isAllCaps = false; setOnClickListener { stopAttention() } }, marginTop(dp(8)))
        root.addView(Button(this).apply { text = "Dismiss"; isAllCaps = false; setOnClickListener { stopAttention(); finish() } }, marginTop(dp(8)))
        setContentView(ScrollView(this).apply { addView(root) })
    }

    private fun stopAttention() { startService(Intent(this, AlertAttentionService::class.java).setAction(AlertAttentionService.ACTION_STOP)) }

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
    private fun marginTop(value: Int) = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { topMargin = value }

    override fun onDestroy() { handler.removeCallbacksAndMessages(null); super.onDestroy() }

    companion object {
        fun fromIntent(intent: Intent) = AlertRecord(
        alertId = intent.getStringExtra(EXTRA_ALERT_ID).orEmpty(), eventId = intent.getStringExtra(EXTRA_EVENT_ID).orEmpty(),
        eventVersion = intent.getIntExtra(EXTRA_EVENT_VERSION, 1), status = intent.getStringExtra(EXTRA_STATUS) ?: "TARGETED",
        deviceId = intent.getStringExtra(EXTRA_DEVICE_ID), createdAtMs = intent.getLongExtra(EXTRA_CREATED_AT, System.currentTimeMillis()),
        acknowledgedAtMs = null, acknowledgementSource = null, provenanceType = intent.getStringExtra(EXTRA_PROVENANCE),
        warningAreaH3 = intent.getStringArrayListExtra(EXTRA_WARNING_AREA).orEmpty(),
        authoritativeRecord = intent.getBooleanExtra(EXTRA_AUTHORITATIVE, true), controlledTest = intent.getBooleanExtra(EXTRA_CONTROLLED, false),
        testMessageId = intent.getStringExtra(EXTRA_TEST_MESSAGE_ID),
        corroboratingDevices = intent.getIntExtra(EXTRA_CORROBORATING_DEVICES, -1).takeIf { it >= 0 },
        corroboratingCells = intent.getIntExtra(EXTRA_CORROBORATING_CELLS, -1).takeIf { it >= 0 },
        )

        const val EXTRA_ALERT_ID = "warning_alert_id"; const val EXTRA_EVENT_ID = "warning_event_id"; const val EXTRA_EVENT_VERSION = "warning_event_version"
        const val EXTRA_STATUS = "warning_status"; const val EXTRA_DEVICE_ID = "warning_device_id"; const val EXTRA_CREATED_AT = "warning_created_at"
        const val EXTRA_PROVENANCE = "warning_provenance"; const val EXTRA_WARNING_AREA = "warning_area_h3"; const val EXTRA_AUTHORITATIVE = "warning_authoritative"
        const val EXTRA_CONTROLLED = "warning_controlled"; const val EXTRA_TITLE = "warning_title"; const val EXTRA_BODY = "warning_body"
        const val EXTRA_TEST_MESSAGE_ID = "warning_test_message_id"
        const val EXTRA_CORROBORATING_DEVICES = "warning_corroborating_devices"; const val EXTRA_CORROBORATING_CELLS = "warning_corroborating_cells"

        fun intent(context: Context, alert: AlertRecord, title: String, body: String) = Intent(context, WarningActivity::class.java)
            .putExtra(EXTRA_ALERT_ID, alert.alertId).putExtra(EXTRA_EVENT_ID, alert.eventId).putExtra(EXTRA_EVENT_VERSION, alert.eventVersion)
            .putExtra(EXTRA_STATUS, alert.status).putExtra(EXTRA_DEVICE_ID, alert.deviceId).putExtra(EXTRA_CREATED_AT, alert.createdAtMs)
            .putExtra(EXTRA_PROVENANCE, alert.provenanceType).putStringArrayListExtra(EXTRA_WARNING_AREA, ArrayList(alert.warningAreaH3))
            .putExtra(EXTRA_AUTHORITATIVE, alert.authoritativeRecord).putExtra(EXTRA_CONTROLLED, alert.controlledTest)
            .putExtra(EXTRA_TEST_MESSAGE_ID, alert.testMessageId)
            .putExtra(EXTRA_CORROBORATING_DEVICES, alert.corroboratingDevices ?: -1).putExtra(EXTRA_CORROBORATING_CELLS, alert.corroboratingCells ?: -1)
            .putExtra(EXTRA_TITLE, title).putExtra(EXTRA_BODY, body)
    }
}
