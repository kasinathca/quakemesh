package com.quakemesh.app

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity:Activity(){
    private lateinit var status:TextView
    override fun onCreate(savedInstanceState:Bundle?){super.onCreate(savedInstanceState);buildUi();requestNeededPermissions()}
    private fun buildUi(){
        val root=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL;setPadding(56,72,56,56);setBackgroundColor(Color.rgb(247,248,250))}
        root.addView(TextView(this).apply{text="QuakeMesh";textSize=30f;setTextColor(Color.rgb(25,31,38))})
        root.addView(TextView(this).apply{text="Experimental cloud corroboration client";textSize=14f;setTextColor(Color.GRAY);setPadding(0,8,0,48)})
        fun row(label:String,value:String)=TextView(this).apply{text="$label\n$value";textSize=15f;setTextColor(Color.DKGRAY);setPadding(24,20,24,20);setBackgroundColor(Color.WHITE)}
        root.addView(row("DEVICE",DeviceIdentity.id(this)))
        status=row("SENSOR","Stopped");root.addView(status)
        root.addView(TextView(this).apply{text="The phone only submits local motion triggers. Event confirmation is cloud-authoritative and requires geographically diverse devices.";textSize=13f;setTextColor(Color.GRAY);setPadding(0,32,0,32)})
        val start=Button(this).apply{text="Start monitoring";setOnClickListener{startMonitoring()}}
        val stop=Button(this).apply{text="Stop monitoring";setOnClickListener{stopService(Intent(this@MainActivity,SensorService::class.java));status.text="SENSOR\nStopped"}}
        root.addView(start);root.addView(stop);setContentView(root)
    }
    private fun requestNeededPermissions(){
        val p=mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION)
        if(Build.VERSION.SDK_INT>=33)p.add(Manifest.permission.POST_NOTIFICATIONS)
        requestPermissions(p.toTypedArray(),100)
    }
    private fun startMonitoring(){
        if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)!=PackageManager.PERMISSION_GRANTED){requestNeededPermissions();return}
        val i=Intent(this,SensorService::class.java);if(Build.VERSION.SDK_INT>=26)startForegroundService(i) else startService(i);status.text="SENSOR\nMonitoring"
    }
}
