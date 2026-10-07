package com.quakemesh.app

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ApiModelsTest {
    @Test
    fun successEnvelopePreservesRequestIdentityAndObservationState() {
        val (requestId, data) = ApiJson.success(
            """{
                "schema_version":"2.0",
                "request_id":"request-123",
                "data":{"accepted":false,"duplicate":true,"event":{"event_id":"event-7"}}
            }""".trimIndent(),
        )

        val receipt = ApiJson.observation(data)
        assertEquals("request-123", requestId)
        assertFalse(receipt.accepted)
        assertTrue(receipt.duplicate)
        assertEquals("event-7", receipt.eventId)
    }

    @Test(expected = IllegalArgumentException::class)
    fun successEnvelopeRejectsNonV2Schema() {
        ApiJson.success("""{"schema_version":"1.0","request_id":"r","data":{}}""")
    }

    @Test
    fun structuredFailurePreservesServerDiagnostics() {
        val failure = ApiJson.failure(
            409,
            """{
                "schema_version":"2.0",
                "error":{
                    "code":"SEQUENCE_REPLAY",
                    "message":"Sequence was already accepted.",
                    "request_id":"request-409",
                    "details":{"last_seq":41,"received_seq":40}
                }
            }""".trimIndent(),
        )

        assertEquals(409, failure.httpStatus)
        assertEquals("SEQUENCE_REPLAY", failure.code)
        assertEquals("request-409", failure.requestId)
        assertEquals("41", failure.details["last_seq"])
        assertEquals(ApiFailure.Kind.SERVER, failure.kind)
    }

    @Test
    fun malformedFailureFallsBackWithoutInventingRequestId() {
        val failure = ApiJson.failure(502, "not-json")

        assertEquals("HTTP_ERROR", failure.code)
        assertEquals("The server returned HTTP 502.", failure.message)
        assertNull(failure.requestId)
    }

    @Test
    fun alertAndAcknowledgementKeepAuthoritativeAlertIdentity() {
        val data = JSONObject(
            """{
                "alert":{
                    "alert_id":"event-9:device-2",
                    "event_id":"event-9",
                    "event_version":3,
                    "status":"ACKNOWLEDGED",
                    "device_id":"device-2",
                    "created_at_ms":1700000000000,
                    "acknowledged_at_ms":1700000005000,
                    "acknowledgement_source":"android"
                },
                "transition_created":true
            }""".trimIndent(),
        )

        val receipt = ApiJson.acknowledgement(data)
        assertTrue(receipt.transitionCreated)
        assertEquals("event-9:device-2", receipt.alert.alertId)
        assertEquals("event-9", receipt.alert.eventId)
        assertEquals(3, receipt.alert.eventVersion)
        assertEquals("device-2", receipt.alert.deviceId)
        assertEquals(1700000005000, receipt.alert.acknowledgedAtMs)
        assertEquals("android", receipt.alert.acknowledgementSource)
    }
}
