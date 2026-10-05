package com.quakemesh.app

import android.app.NotificationManager
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

class QuakeMessagingService:FirebaseMessagingService(){
    private fun firstDelivery(eventId:String?):Boolean{
        if(eventId.isNullOrBlank())return true
        val prefs=getSharedPreferences("quakemesh_alert_dedupe",MODE_PRIVATE)
        val key="event:$eventId"
        if(prefs.getBoolean(key,false))return false
        prefs.edit().putBoolean(key,true).apply()
        return true
    }
    override fun onMessageReceived(message:RemoteMessage){
        val eventId=message.data["event_id"]
        if(!firstDelivery(eventId))return
        val title=message.notification?.title?:"QuakeMesh alert"
        val body=message.notification?.body?:"Corroborated ground-motion evidence detected in your warning region."
        val notification=NotificationHelper.warning(this,title,body,eventId)
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).notify((System.currentTimeMillis()%Int.MAX_VALUE).toInt(),notification)
    }
    override fun onNewToken(token:String){super.onNewToken(token)}
}
