package com.quakemesh.app

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import java.text.DateFormat
import java.util.Date
import java.util.Locale

class MainActivity : Activity() {
    private val handler = Handler(Looper.getMainLooper())
    private val values = mutableMapOf<String, TextView>()
    private lateinit var startButton: Button
    private lateinit var stopButton: Button
    private lateinit var acknowledgeButton: Button
    private var receiverRegistered = false
    private val stateReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) = render()
    }
    private val refreshTask = object : Runnable {
        override fun run() {
            refreshAlerts()
            handler.postDelayed(this, 10_000L)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildUi()
        requestNeededPermissions()
        render()
    }

    @SuppressLint("UnspecifiedRegisterReceiverFlag")
    override fun onStart() {
        super.onStart()
        val filter = IntentFilter(MonitoringState.ACTION_CHANGED)
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(stateReceiver, filter, RECEIVER_NOT_EXPORTED)
        else @Suppress("DEPRECATION") registerReceiver(stateReceiver, filter)
        receiverRegistered = true
        handler.post(refreshTask)
    }

    override fun onStop() {
        handler.removeCallbacks(refreshTask)
        if (receiverRegistered) unregisterReceiver(stateReceiver)
        receiverRegistered = false
        super.onStop()
    }

    private fun buildUi() {
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(28), dp(20), dp(36))
            setBackgroundColor(Color.rgb(244, 246, 248))
        }
        content.addView(TextView(this).apply {
            text = "QuakeMesh"
            textSize = 30f
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
            setTextColor(Color.rgb(20, 31, 43))
        })
        content.addView(TextView(this).apply {
            text = "Experimental ground-motion corroboration"
            textSize = 15f
            setTextColor(Color.rgb(70, 86, 101))
            setPadding(0, dp(4), 0, dp(8))
        })
        content.addView(TextView(this).apply {
            text = "Research system — not an official earthquake early-warning service."
            textSize = 12f
            setTextColor(Color.rgb(124, 74, 32))
            setPadding(0, 0, 0, dp(20))
        })

        content.addView(section("MONITORING", listOf(
            "monitoring" to "Status",
            "device" to "Device ID",
            "environment" to "Environment",
            "api" to "API state",
            "sensor" to "Sensor state",
            "location" to "Location state",
            "heartbeat" to "Latest heartbeat",
        )))
        content.addView(section("LOCAL MOTION OBSERVED", listOf(
            "motion" to "Device observation",
            "motion_metrics" to "Latest local signal",
        ), Color.rgb(42, 88, 126)))
        content.addView(TextView(this).apply {
            text = "Local motion is a device observation only. It does not confirm an event."
            textSize = 12f
            setTextColor(Color.rgb(70, 86, 101))
            setPadding(dp(4), dp(8), dp(4), dp(16))
        })
        content.addView(section("CLOUD-CORROBORATED EVENT", listOf(
            "alert" to "Latest alert",
            "event" to "Event identity",
            "alert_status" to "Delivery / acknowledgement",
        ), Color.rgb(150, 54, 45)))
        content.addView(TextView(this).apply {
            text = "Cloud corroboration requires distinct devices and spatially diverse H3 cells."
            textSize = 12f
            setTextColor(Color.rgb(70, 86, 101))
            setPadding(dp(4), dp(8), dp(4), dp(18))
        })

        val actions = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        startButton = actionButton("Start monitoring", Color.rgb(38, 91, 75)) { startMonitoring() }
        stopButton = actionButton("Stop monitoring", Color.rgb(73, 86, 98)) { stopMonitoring() }
        acknowledgeButton = actionButton("Acknowledge latest alert", Color.rgb(150, 54, 45)) { acknowledgeLatest() }
        actions.addView(startButton)
        actions.addView(stopButton, marginTop(dp(8)))
        actions.addView(acknowledgeButton, marginTop(dp(8)))
        content.addView(actions)
        setContentView(ScrollView(this).apply { addView(content) })
    }

    private fun section(title: String, rows: List<Pair<String, String>>, accent: Int = Color.rgb(38, 91, 75)): View {
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(16), dp(18), dp(12))
            background = GradientDrawable().apply {
                setColor(Color.WHITE)
                cornerRadius = dp(12).toFloat()
                setStroke(dp(1), Color.rgb(220, 226, 231))
            }
            addView(TextView(this@MainActivity).apply {
                text = title
                textSize = 12f
                letterSpacing = .08f
                typeface = Typeface.DEFAULT_BOLD
                setTextColor(accent)
                setPadding(0, 0, 0, dp(8))
            })
            rows.forEach { (key, label) ->
                addView(TextView(this@MainActivity).apply {
                    text = label
                    textSize = 11f
                    setTextColor(Color.rgb(104, 117, 128))
                    setPadding(0, dp(7), 0, 0)
                })
                addView(TextView(this@MainActivity).apply {
                    text = "—"
                    textSize = 15f
                    setTextColor(Color.rgb(27, 39, 51))
                    values[key] = this
                })
            }
        }.also { it.layoutParams = marginBottom(dp(12)) }
    }

    private fun actionButton(label: String, color: Int, action: () -> Unit) = Button(this).apply {
        text = label
        isAllCaps = false
        textSize = 15f
        setTextColor(Color.WHITE)
        gravity = Gravity.CENTER
        backgroundTintList = android.content.res.ColorStateList.valueOf(color)
        setOnClickListener { action() }
    }

    private fun render() {
        val snapshot = MonitoringState.snapshot(this)
        values["monitoring"]?.text = if (snapshot.monitoring) "Active" else "Stopped"
        values["device"]?.text = DeviceIdentity.id(this)
        values["environment"]?.text = AppConfig.environmentLabel
        values["api"]?.text = when {
            snapshot.apiFailure != null -> "${snapshot.apiFailure.code}: ${snapshot.apiFailure.message}"
            snapshot.latestHeartbeatAtMs != null -> "Connected · request ${snapshot.latestHeartbeatRequestId?.take(8) ?: "received"}"
            AppConfig.configured -> "Configured · awaiting successful heartbeat"
            else -> "Not configured"
        }
        values["sensor"]?.text = when {
            !snapshot.sensorAvailable -> "Accelerometer unavailable"
            snapshot.monitoring -> "Accelerometer monitoring active"
            else -> "Stopped"
        }
        values["location"]?.text = snapshot.locationState
        values["heartbeat"]?.text = formatTime(snapshot.latestHeartbeatAtMs)
        values["motion"]?.text = if (snapshot.localMotionAtMs == null) "No threshold-crossing motion observed" else formatTime(snapshot.localMotionAtMs)
        values["motion_metrics"]?.text = if (snapshot.localMotionRms == null) "RMS / peak —" else String.format(
            Locale.US, "RMS %.2f m/s² · peak %.2f m/s²", snapshot.localMotionRms, snapshot.localMotionPeak,
        )
        val alert = snapshot.latestAlert
        values["alert"]?.text = alert?.let { "${it.status} · ${formatTime(it.createdAtMs)}" } ?: "No corroborated alert received"
        values["event"]?.text = alert?.let { "${it.eventId} · version ${it.eventVersion}\nAlert ${it.alertId}" } ?: "—"
        values["alert_status"]?.text = alert?.let {
            if (it.acknowledgedAtMs != null) "Acknowledged ${formatTime(it.acknowledgedAtMs)} via ${it.acknowledgementSource ?: "android"}" else "Awaiting acknowledgement"
        } ?: "—"
        startButton.isEnabled = !snapshot.monitoring
        stopButton.isEnabled = snapshot.monitoring
        acknowledgeButton.isEnabled = alert != null && alert.acknowledgedAtMs == null && !alert.alertId.startsWith("legacy:")
    }

    private fun refreshAlerts() {
        val deviceId = DeviceIdentity.id(this)
        ApiClient.alerts { result ->
            when (result) {
                is ApiResult.Success -> result.data
                    .filter { it.deviceId == deviceId }
                    .maxByOrNull { it.createdAtMs }
                    ?.let { MonitoringState.recordAlert(this, it) }
                is ApiResult.Failure -> MonitoringState.update(this) { it.copy(apiFailure = result.error) }
            }
        }
    }

    private fun acknowledgeLatest() {
        val alert = MonitoringState.snapshot(this).latestAlert ?: return
        acknowledgeButton.isEnabled = false
        ApiClient.acknowledge(alert.alertId, DeviceIdentity.id(this)) { result ->
            when (result) {
                is ApiResult.Success -> MonitoringState.recordAlert(this, result.data.alert)
                is ApiResult.Failure -> MonitoringState.update(this) { it.copy(apiFailure = result.error) }
            }
        }
    }

    private fun requestNeededPermissions() {
        val permissions = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION)
        if (Build.VERSION.SDK_INT >= 33) permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        val missing = permissions.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) requestPermissions(missing.toTypedArray(), PERMISSION_REQUEST)
    }

    private fun startMonitoring() {
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            requestNeededPermissions()
            return
        }
        val intent = Intent(this, SensorService::class.java)
        startForegroundService(intent)
    }

    private fun stopMonitoring() {
        stopService(Intent(this, SensorService::class.java))
        MonitoringState.update(this) { it.copy(monitoring = false) }
    }

    private fun formatTime(epochMs: Long?): String = epochMs?.let {
        DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.MEDIUM).format(Date(it))
    } ?: "Not yet"

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
    private fun marginBottom(value: Int) = LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT,
    ).apply { bottomMargin = value }
    private fun marginTop(value: Int) = LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT,
    ).apply { topMargin = value }

    companion object { private const val PERMISSION_REQUEST = 100 }
}
