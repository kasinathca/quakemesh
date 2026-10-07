package com.quakemesh.app

import org.json.JSONObject
import org.json.JSONException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URI
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

object ApiClient {
    private const val TIMEOUT_MS = 8_000
    private val executor: ExecutorService = Executors.newFixedThreadPool(2)

    fun heartbeat(
        deviceId: String,
        seq: Long,
        latitude: Double,
        longitude: Double,
        fcmToken: String?,
        callback: (ApiResult<ObservationReceipt>) -> Unit = {},
    ) {
        val body = observation(deviceId, seq, latitude, longitude)
        if (!fcmToken.isNullOrBlank()) body.put("fcm_token", fcmToken)
        request("POST", "/v1/devices/heartbeat", body, ApiJson::observation, callback)
    }

    fun trigger(
        deviceId: String,
        seq: Long,
        latitude: Double,
        longitude: Double,
        rms: Double,
        peak: Double,
        callback: (ApiResult<ObservationReceipt>) -> Unit = {},
    ) {
        val body = observation(deviceId, seq, latitude, longitude)
            .put("motion_rms", rms)
            .put("motion_peak", peak)
        request("POST", "/v1/evidence/trigger", body, ApiJson::observation, callback)
    }

    fun alerts(callback: (ApiResult<List<AlertRecord>>) -> Unit) {
        request("GET", "/v1/alerts?limit=200", null, ApiJson::alerts, callback)
    }

    fun acknowledge(
        alertId: String,
        deviceId: String,
        callback: (ApiResult<AcknowledgementReceipt>) -> Unit,
    ) {
        val encodedId = URLEncoder.encode(alertId, StandardCharsets.UTF_8.toString())
        val body = JSONObject()
            .put("acknowledgement_source", "android")
            .put("device_id", deviceId)
        request("POST", "/v1/alerts/$encodedId/ack", body, ApiJson::acknowledgement, callback)
    }

    private fun observation(deviceId: String, seq: Long, latitude: Double, longitude: Double) =
        JSONObject()
            .put("schema_version", "1.0")
            .put("device_id", deviceId)
            .put("seq", seq)
            .put("observed_at_ms", System.currentTimeMillis())
            .put("latitude", latitude)
            .put("longitude", longitude)

    private fun <T> request(
        method: String,
        path: String,
        body: JSONObject?,
        decode: (JSONObject) -> T,
        callback: (ApiResult<T>) -> Unit,
    ) {
        val baseUrl = AppConfig.baseUrl
        if (baseUrl.isBlank()) {
            callback(ApiResult.Failure(ApiFailure(
                code = "API_NOT_CONFIGURED",
                message = "Configure QUAKEMESH_API_BASE_URL for this build.",
                kind = ApiFailure.Kind.CONFIGURATION,
            )))
            return
        }
        executor.execute {
            var connection: HttpURLConnection? = null
            val result = try {
                val target = URI.create(baseUrl + path).toURL()
                connection = (target.openConnection() as HttpURLConnection).apply {
                    requestMethod = method
                    connectTimeout = TIMEOUT_MS
                    readTimeout = TIMEOUT_MS
                    setRequestProperty("Accept", "application/json")
                    if (BuildConfig.QUAKEMESH_API_KEY.isNotBlank()) {
                        setRequestProperty("x-api-key", BuildConfig.QUAKEMESH_API_KEY)
                    }
                    if (body != null) {
                        doOutput = true
                        setRequestProperty("Content-Type", "application/json")
                        outputStream.use { it.write(body.toString().toByteArray(StandardCharsets.UTF_8)) }
                    }
                }
                val status = connection.responseCode
                val stream = if (status in 200..299) connection.inputStream else connection.errorStream
                val responseBody = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
                if (status !in 200..299) {
                    ApiResult.Failure(ApiJson.failure(status, responseBody))
                } else {
                    val (requestId, data) = ApiJson.success(responseBody)
                    ApiResult.Success(decode(data), requestId)
                }
            } catch (_: SocketTimeoutException) {
                ApiResult.Failure(ApiFailure(
                    code = "REQUEST_TIMEOUT",
                    message = "The QuakeMesh API did not respond within ${TIMEOUT_MS / 1000} seconds.",
                    kind = ApiFailure.Kind.TIMEOUT,
                ))
            } catch (error: JSONException) {
                ApiResult.Failure(ApiFailure(
                    code = "INVALID_API_RESPONSE",
                    message = "The API response was not valid QuakeMesh V2 data.",
                    kind = ApiFailure.Kind.INVALID_RESPONSE,
                ))
            } catch (error: IllegalArgumentException) {
                ApiResult.Failure(ApiFailure(
                    code = "INVALID_API_RESPONSE",
                    message = error.message ?: "The API response was not valid QuakeMesh V2 data.",
                    kind = ApiFailure.Kind.INVALID_RESPONSE,
                ))
            } catch (error: Exception) {
                ApiResult.Failure(ApiFailure(
                    code = "NETWORK_ERROR",
                    message = error.message ?: "Unable to connect to the QuakeMesh API.",
                    kind = ApiFailure.Kind.NETWORK,
                ))
            } finally {
                connection?.disconnect()
            }
            callback(result)
        }
    }
}
