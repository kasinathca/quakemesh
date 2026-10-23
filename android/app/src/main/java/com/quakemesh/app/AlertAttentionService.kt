package com.quakemesh.app

import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.speech.tts.TextToSpeech
import java.util.Locale

class AlertAttentionService : Service(), TextToSpeech.OnInitListener {
    private val handler = Handler(Looper.getMainLooper())
    private var player: MediaPlayer? = null
    private var tts: TextToSpeech? = null
    private var focusRequest: AudioFocusRequest? = null
    private var alertId: String? = null
    private var deviceId: String? = null
    private var stopping = false
    private val stopTask = Runnable { stopAlert() }
    private val speakTask = object : Runnable {
        override fun run() {
            tts?.speak("Alert! Alert! QuakeMesh simulated earthquake drill!", TextToSpeech.QUEUE_FLUSH, null, "quakemesh-drill")
            handler.postDelayed(this, 12_000L)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopAlert()
            return START_NOT_STICKY
        }
        val alert = WarningActivity.fromIntent(intent ?: return START_NOT_STICKY)
        if (player != null || tts != null) releaseAttention(recordReceipt = true)
        stopping = false
        alertId = alert.alertId
        deviceId = alert.deviceId
        val title = intent.getStringExtra(WarningActivity.EXTRA_TITLE) ?: "QUAKEMESH — SIMULATED EARTHQUAKE DRILL"
        val body = intent.getStringExtra(WarningActivity.EXTRA_BODY) ?: "Cloud-corroborated simulation alert."
        startForeground(alert.alertId.hashCode(), NotificationHelper.warning(this, title, body, alert))
        requestAudioFocus()
        val descriptor = resources.openRawResourceFd(R.raw.quakemesh_warning_v1)
        player = MediaPlayer().apply {
            isLooping = true
            setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build())
            setDataSource(descriptor.fileDescriptor, descriptor.startOffset, descriptor.length)
            descriptor.close()
            prepare()
            start()
        }
        vibrate()
        tts = TextToSpeech(this, this)
        handler.postDelayed(stopTask, 90_000L)
        alert.deviceId?.let { ApiClient.alertReceipt(alert.alertId, it, "AUDIO_STARTED") }
        return START_NOT_STICKY
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts?.language = Locale.US
            handler.post(speakTask)
        }
    }

    private fun requestAudioFocus() {
        val audio = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        if (Build.VERSION.SDK_INT >= 26) {
            focusRequest = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE)
                .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).build()).build()
            audio.requestAudioFocus(focusRequest!!)
        } else @Suppress("DEPRECATION") {
            audio.requestAudioFocus(null, AudioManager.STREAM_ALARM, AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE)
        }
    }

    private fun vibrate() {
        val vibrator = if (Build.VERSION.SDK_INT >= 31) (getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator else @Suppress("DEPRECATION") (getSystemService(VIBRATOR_SERVICE) as Vibrator)
        val pattern = longArrayOf(0, 900, 250, 900, 250, 1400)
        if (Build.VERSION.SDK_INT >= 26) vibrator.vibrate(VibrationEffect.createWaveform(pattern, 0)) else @Suppress("DEPRECATION") vibrator.vibrate(pattern, 0)
    }

    private fun stopAlert() {
        if (stopping) return
        stopping = true
        releaseAttention(recordReceipt = true)
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun releaseAttention(recordReceipt: Boolean) {
        handler.removeCallbacks(stopTask)
        handler.removeCallbacks(speakTask)
        player?.stop(); player?.release(); player = null
        tts?.stop(); tts?.shutdown(); tts = null
        val vibrator = if (Build.VERSION.SDK_INT >= 31) (getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator else @Suppress("DEPRECATION") (getSystemService(VIBRATOR_SERVICE) as Vibrator)
        vibrator.cancel()
        focusRequest?.let { (getSystemService(AUDIO_SERVICE) as AudioManager).abandonAudioFocusRequest(it) }
        focusRequest = null
        val id = alertId; val device = deviceId
        if (recordReceipt && id != null && device != null) ApiClient.alertReceipt(id, device, "AUDIO_STOPPED")
        alertId = null
        deviceId = null
    }

    override fun onDestroy() {
        if (!stopping) releaseAttention(recordReceipt = true)
        super.onDestroy()
    }

    companion object {
        const val ACTION_STOP = "com.quakemesh.app.STOP_ALERT"
        fun startIntent(context: Context, alert: AlertRecord, title: String, body: String): Intent =
            WarningActivity.intent(context, alert, title, body).setClass(context, AlertAttentionService::class.java)
    }
}
