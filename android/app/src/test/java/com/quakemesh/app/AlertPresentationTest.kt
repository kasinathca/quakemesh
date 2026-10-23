package com.quakemesh.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AlertPresentationTest {
    private fun alert(provenance: String? = "physical", controlled: Boolean = false, authoritative: Boolean = true, id: String = "event-1:device-1") =
        AlertRecord(id, "event-1", 1, if (controlled) "CONTROLLED_TEST" else "SENT", "device-1", 1L, null, null, provenance, listOf("8761892c9ffffff"), authoritative, controlled)

    @Test fun physicalAndSimulationProvenanceRemainDistinct() {
        assertEquals(AlertKind.AUTHORITATIVE_PHYSICAL, AlertPresentationPolicy.classify(alert()))
        assertEquals(AlertKind.AUTHORITATIVE_SIMULATION, AlertPresentationPolicy.classify(alert("scenario")))
    }

    @Test fun controlledPreviewUsesDistinctChannelAndCannotAcknowledge() {
        val presentation = AlertPresentationPolicy.forAlert(alert(controlled = true, authoritative = false))
        assertEquals(NotificationHelper.DEMO_CHANNEL, presentation.channelId)
        assertFalse(presentation.canAcknowledge)
        assertFalse(presentation.requestFullScreen)
        assertTrue(presentation.headsUp)
    }

    @Test fun warningMonitoringAndDemoChannelsAreVersionedAndDistinct() {
        assertEquals(3, setOf(NotificationHelper.ALERT_CHANNEL, NotificationHelper.DEMO_CHANNEL, NotificationHelper.MONITOR_CHANNEL).size)
        assertTrue(NotificationHelper.ALERT_CHANNEL.endsWith("_v3"))
        assertTrue(NotificationHelper.DEMO_CHANNEL.endsWith("_v1"))
    }

    @Test fun repeatedDeliveryUsesStableDeduplicationKey() {
        assertEquals("alert:a-1", AlertDeliveryKey.forMessage("a-1", "event-1"))
        assertEquals(AlertDeliveryKey.forMessage("a-1", "event-1"), AlertDeliveryKey.forMessage("a-1", "event-1"))
        assertEquals("legacy-event:event-1", AlertDeliveryKey.forMessage("", "event-1"))
    }

    @Test fun runtimeNotificationPermissionMatchesAndroidPolicy() {
        assertFalse(NotificationPermissionPolicy.requiresRuntimePermission(32))
        assertTrue(NotificationPermissionPolicy.requiresRuntimePermission(33))
    }

    @Test fun authoritativeAlertRequestsFullScreenAndKeepsHeadsUpFallbackAndAck() {
        val presentation = AlertPresentationPolicy.forAlert(alert())
        assertEquals(NotificationHelper.ALERT_CHANNEL, presentation.channelId)
        assertTrue(presentation.canAcknowledge)
        assertTrue(presentation.requestFullScreen)
    }

    @Test fun controlledWarningToneRemainsNonAuthoritative() {
        val controlled = alert(controlled = true, authoritative = false, id = "warning-tone-preview")
        assertFalse(AlertPresentationPolicy.forAlert(controlled).canAcknowledge)
        assertEquals(AlertKind.CONTROLLED_TEST, AlertPresentationPolicy.classify(controlled))
    }
}
