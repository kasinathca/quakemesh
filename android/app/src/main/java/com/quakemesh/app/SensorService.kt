package com.quakemesh.app

import android.Manifest
import android.app.*
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.hardware.*
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.IBinder
import android.util.Log
import com.google.firebase.messaging.FirebaseMessaging
import kotlin.math.abs
import kotlin.math.sqrt

class SensorService:Service(),SensorEventListener,LocationListener{
    private lateinit var sm:SensorManager;private lateinit var lm:LocationManager
    private val deviations=ArrayDeque<Double>();private var lastLocation:Location?=null;private var lastTriggerAt=0L;private var lastHeartbeatAt=0L;private val gravity=9.80665
    private val rmsThreshold=.75;private val peakThreshold=1.80;private val windowSize=100;private val triggerCooldownMs=8_000L
    override fun onCreate(){
        super.onCreate();NotificationHelper.ensureChannel(this);startForeground(7001,NotificationHelper.monitoring(this));
        sm=getSystemService(SENSOR_SERVICE) as SensorManager;lm=getSystemService(LOCATION_SERVICE) as LocationManager
        sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)?.let{sm.registerListener(this,it,SensorManager.SENSOR_DELAY_GAME)}
        if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED){
            try{lm.requestLocationUpdates(LocationManager.GPS_PROVIDER,2000,1f,this);lastLocation=lm.getLastKnownLocation(LocationManager.GPS_PROVIDER)?:lm.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)}catch(e:Exception){Log.e("QuakeMesh","location",e)}
        }
        sendHeartbeat()
    }
    override fun onDestroy(){sm.unregisterListener(this);try{lm.removeUpdates(this)}catch(_:Exception){};super.onDestroy()}
    override fun onBind(intent:Intent?):IBinder?=null
    override fun onAccuracyChanged(sensor:Sensor?,accuracy:Int){}
    override fun onLocationChanged(location:Location){lastLocation=location;if(System.currentTimeMillis()-lastHeartbeatAt>30_000)sendHeartbeat()}
    @Deprecated("legacy callbacks") override fun onStatusChanged(provider:String?,status:Int,extras:Bundle?){}
    override fun onProviderEnabled(provider:String){};override fun onProviderDisabled(provider:String){}
    override fun onSensorChanged(event:SensorEvent){
        val x=event.values[0].toDouble();val y=event.values[1].toDouble();val z=event.values[2].toDouble();val dev=abs(sqrt(x*x+y*y+z*z)-gravity)
        deviations.addLast(dev);while(deviations.size>windowSize)deviations.removeFirst();if(deviations.size<windowSize)return
        val rms=sqrt(deviations.sumOf{it*it}/deviations.size);val peak=deviations.maxOrNull()?:0.0;val now=System.currentTimeMillis()
        if(rms>=rmsThreshold&&peak>=peakThreshold&&now-lastTriggerAt>=triggerCooldownMs){
            val l=lastLocation?:return;lastTriggerAt=now;ApiClient.trigger(DeviceIdentity.id(this),DeviceIdentity.nextSeq(this),l.latitude,l.longitude,rms,peak)
        }
    }
    private fun sendHeartbeat(){
        val l=lastLocation?:return;lastHeartbeatAt=System.currentTimeMillis();FirebaseMessaging.getInstance().token.addOnCompleteListener{task->
            val token=if(task.isSuccessful)task.result else null;ApiClient.heartbeat(DeviceIdentity.id(this),DeviceIdentity.nextSeq(this),l.latitude,l.longitude,token)
        }
    }
}
