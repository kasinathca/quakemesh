package com.quakemesh.app

object AppConfig {
    val baseUrl: String
        get() = BuildConfig.QUAKEMESH_API_BASE_URL.trim().trimEnd('/').ifBlank {
            if (BuildConfig.DEBUG) "http://10.0.2.2:8000" else ""
        }

    val environmentLabel: String
        get() = when {
            baseUrl.contains("10.0.2.2") || baseUrl.contains("127.0.0.1") || baseUrl.contains("localhost") -> "Local V2"
            baseUrl.isBlank() -> "Not configured"
            else -> "Remote V2"
        }

    val configured: Boolean get() = baseUrl.isNotBlank()
}
