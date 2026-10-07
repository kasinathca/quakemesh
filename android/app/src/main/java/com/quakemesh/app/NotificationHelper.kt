package com.quakemesh.app

import android.app.*
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.media.AudioAttributes
import android.provider.Settings

object NotificationHelper{
    const val ALERT_CHANNEL="quakemesh_alerts";const val MONITOR_CHANNEL="quakemesh_monitoring"
    fun ensureChannel(c:Context){
        val nm=c.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(NotificationChannel(MONITOR_CHANNEL,"QuakeMesh monitoring",NotificationManager.IMPORTANCE_LOW).apply{description="Foreground sensor monitoring"})
        nm.createNotificationChannel(NotificationChannel(ALERT_CHANNEL,"QuakeMesh warnings",NotificationManager.IMPORTANCE_HIGH).apply{description="Corroborated QuakeMesh warning notifications";enableVibration(true);vibrationPattern=longArrayOf(0,700,300,700);setSound(Settings.System.DEFAULT_ALARM_ALERT_URI,AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).build());lightColor=Color.RED;enableLights(true)})
    }
    fun monitoring(c:Context):Notification{ensureChannel(c);return Notification.Builder(c,MONITOR_CHANNEL).setSmallIcon(android.R.drawable.ic_menu_compass).setContentTitle("QuakeMesh monitoring").setContentText("Accelerometer and location trigger detection active").setOngoing(true).build()}
    fun warning(c:Context,title:String,body:String,alert:AlertRecord):Notification{
        ensureChannel(c)
        val intent=Intent(c,MainActivity::class.java).putExtra("alert_id",alert.alertId)
        val pi=PendingIntent.getActivity(c,alert.alertId.hashCode(),intent,PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val detail="$body\nEvent: ${alert.eventId}\nAlert: ${alert.alertId}"
        return Notification.Builder(c,ALERT_CHANNEL).setSmallIcon(android.R.drawable.ic_dialog_alert).setContentTitle(title).setContentText(body).setStyle(Notification.BigTextStyle().bigText(detail)).setCategory(Notification.CATEGORY_ALARM).setPriority(Notification.PRIORITY_MAX).setAutoCancel(true).setContentIntent(pi).build()
    }
}
