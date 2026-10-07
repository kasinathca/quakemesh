package com.quakemesh.app

import org.json.JSONArray
import org.json.JSONObject

data class ApiFailure(
    val httpStatus: Int? = null,
    val code: String,
    val message: String,
    val requestId: String? = null,
    val details: Map<String, String> = emptyMap(),
    val kind: Kind,
) {
    enum class Kind { SERVER, NETWORK, TIMEOUT, INVALID_RESPONSE, CONFIGURATION }
}

sealed interface ApiResult<out T> {
    data class Success<T>(val data: T, val requestId: String) : ApiResult<T>
    data class Failure(val error: ApiFailure) : ApiResult<Nothing>
}

data class ObservationReceipt(
    val accepted: Boolean,
    val duplicate: Boolean,
    val eventId: String?,
)

data class AlertRecord(
    val alertId: String,
    val eventId: String,
    val eventVersion: Int,
    val status: String,
    val deviceId: String?,
    val createdAtMs: Long,
    val acknowledgedAtMs: Long?,
    val acknowledgementSource: String?,
)

data class AcknowledgementReceipt(
    val alert: AlertRecord,
    val transitionCreated: Boolean,
)

internal object ApiJson {
    fun success(body: String): Pair<String, JSONObject> {
        val envelope = JSONObject(body)
        require(envelope.optString("schema_version") == "2.0") { "Unsupported response schema" }
        val requestId = envelope.getString("request_id")
        return requestId to envelope.getJSONObject("data")
    }

    fun failure(status: Int, body: String): ApiFailure {
        return try {
            val error = JSONObject(body).getJSONObject("error")
            ApiFailure(
                httpStatus = status,
                code = error.optString("code", "HTTP_ERROR"),
                message = error.optString("message", "The server rejected the request."),
                requestId = error.optString("request_id").ifBlank { null },
                details = stringMap(error.optJSONObject("details")),
                kind = ApiFailure.Kind.SERVER,
            )
        } catch (_: Exception) {
            ApiFailure(status, "HTTP_ERROR", "The server returned HTTP $status.", kind = ApiFailure.Kind.SERVER)
        }
    }

    fun observation(data: JSONObject) = ObservationReceipt(
        accepted = data.optBoolean("accepted", true),
        duplicate = data.optBoolean("duplicate", false),
        eventId = data.optJSONObject("event")?.optString("event_id")?.ifBlank { null },
    )

    fun alerts(data: JSONObject): List<AlertRecord> {
        val items = data.optJSONArray("items") ?: JSONArray()
        return buildList {
            for (index in 0 until items.length()) add(alert(items.getJSONObject(index)))
        }
    }

    fun acknowledgement(data: JSONObject) = AcknowledgementReceipt(
        alert = alert(data.getJSONObject("alert")),
        transitionCreated = data.optBoolean("transition_created"),
    )

    fun alert(value: JSONObject) = AlertRecord(
        alertId = value.getString("alert_id"),
        eventId = value.getString("event_id"),
        eventVersion = value.optInt("event_version", 1),
        status = value.optString("status", "TARGETED"),
        deviceId = value.optString("device_id").ifBlank { null },
        createdAtMs = value.optLong("created_at_ms", value.optLong("received_at_ms", 0L)),
        acknowledgedAtMs = value.optLongOrNull("acknowledged_at_ms"),
        acknowledgementSource = value.optString("acknowledgement_source").ifBlank { null },
    )

    private fun JSONObject.optLongOrNull(key: String): Long? =
        if (has(key) && !isNull(key)) optLong(key) else null

    private fun stringMap(value: JSONObject?): Map<String, String> {
        if (value == null) return emptyMap()
        return buildMap { value.keys().forEach { key -> put(key, value.opt(key)?.toString().orEmpty()) } }
    }
}
