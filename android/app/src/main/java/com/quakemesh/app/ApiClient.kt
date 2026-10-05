package com.quakemesh.app

import android.util.Log
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

object ApiClient {
    private val executor=Executors.newSingleThreadExecutor()
    private fun post(path:String,body:JSONObject){
        val base=BuildConfig.QUAKEMESH_API_BASE_URL.trimEnd('/')
        if(base.isBlank()||BuildConfig.QUAKEMESH_API_KEY.isBlank()){ Log.w("QuakeMesh","API configuration missing; not uploading");return }
        executor.execute {
            var c:HttpURLConnection?=null
            try {
                c=(URL(base+path).openConnection() as HttpURLConnection).apply {
                    requestMethod="POST";connectTimeout=8000;readTimeout=8000;doOutput=true
                    setRequestProperty("Content-Type","application/json");setRequestProperty("x-api-key",BuildConfig.QUAKEMESH_API_KEY)
                }
                c.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
                val code=c.responseCode
                if(code !in 200..299) Log.w("QuakeMesh","HTTP $code ${c.errorStream?.bufferedReader()?.readText()}")
            } catch(e:Exception){Log.e("QuakeMesh","upload failed",e)} finally {c?.disconnect()}
        }
    }
    fun heartbeat(deviceId:String,seq:Long,lat:Double,lon:Double,fcmToken:String?){
        val j=JSONObject().put("schema_version","1.0").put("device_id",deviceId).put("seq",seq).put("observed_at_ms",System.currentTimeMillis()).put("latitude",lat).put("longitude",lon)
        if(!fcmToken.isNullOrBlank())j.put("fcm_token",fcmToken);post("/v1/devices/heartbeat",j)
    }
    fun trigger(deviceId:String,seq:Long,lat:Double,lon:Double,rms:Double,peak:Double){
        val j=JSONObject().put("schema_version","1.0").put("device_id",deviceId).put("seq",seq).put("observed_at_ms",System.currentTimeMillis()).put("latitude",lat).put("longitude",lon).put("motion_rms",rms).put("motion_peak",peak)
        post("/v1/evidence/trigger",j)
    }
}
