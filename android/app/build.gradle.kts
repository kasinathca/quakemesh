import java.util.Properties

plugins {
    id("com.android.application")
}

val googleServicesFile = file("google-services.json")

if (googleServicesFile.exists()) {
    pluginManager.apply("com.google.gms.google-services")
}

val localProps=Properties().apply {
    val f=rootProject.file("local.properties")
    if(f.exists()) f.inputStream().use { load(it) }
}
fun q(value:String)="\""+value.replace("\\","\\\\").replace("\"","\\\"")+"\""

android {
    namespace="com.quakemesh.app"
    compileSdk=37
    defaultConfig {
    applicationId = "com.quakemesh.app"
    minSdk = 26
    targetSdk = 37
    versionCode = 2
    versionName = "1.0.1"

    buildConfigField(
        "String",
        "QUAKEMESH_API_BASE_URL",
        q(localProps.getProperty("QUAKEMESH_API_BASE_URL", ""))
    )

    buildConfigField(
        "String",
        "QUAKEMESH_API_KEY",
        q(localProps.getProperty("QUAKEMESH_API_KEY", ""))
    )

    buildConfigField(
        "boolean",
        "QUAKEMESH_FIREBASE_ENABLED",
        googleServicesFile.exists().toString()
    )
}
    buildFeatures { buildConfig=true }
    compileOptions { sourceCompatibility=JavaVersion.VERSION_17; targetCompatibility=JavaVersion.VERSION_17 }
    testOptions { unitTests.isReturnDefaultValues = true }
}

dependencies {
    implementation(platform("com.google.firebase:firebase-bom:34.18.0"))
    implementation("com.google.firebase:firebase-messaging")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
