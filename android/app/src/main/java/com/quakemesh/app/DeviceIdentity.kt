package com.quakemesh.app

import android.content.Context
import java.util.UUID

object DeviceIdentity {
    fun id(context:Context):String {
        val p=context.getSharedPreferences("quakemesh",Context.MODE_PRIVATE)
        return p.getString("device_id",null) ?: ("QM-ANDROID-"+UUID.randomUUID().toString().substring(0,12)).also { p.edit().putString("device_id",it).apply() }
    }
    @Synchronized fun nextSeq(context:Context):Long {
        val p=context.getSharedPreferences("quakemesh",Context.MODE_PRIVATE);val v=p.getLong("seq",0)+1;p.edit().putLong("seq",v).apply();return v
    }
}
