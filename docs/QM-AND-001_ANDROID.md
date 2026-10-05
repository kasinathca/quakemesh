# QM-AND-001 — Android Client

## Runtime role

The Android app is an edge trigger source and warning recipient. It does **not** make authoritative event decisions.

## Monitoring

A foreground `SensorService`:

- listens to the accelerometer;
- maintains a fixed sample window;
- computes deviation from gravity, RMS and peak;
- applies an experimental local prefilter;
- obtains device location;
- submits a trigger after the gate and cooldown pass;
- periodically sends heartbeat/presence;
- includes the current FCM token in heartbeat when available.

The local motion gate only limits upload frequency; cloud corroboration remains mandatory.

## Notification

`QuakeMessagingService` receives FCM messages and creates a high-importance warning notification channel with alarm-like sound/vibration where Android permits it.

## Current build baseline

- Android Gradle Plugin 9.4.0;
- Gradle 9.6.0;
- JDK 17;
- compile/target SDK 37;
- minimum SDK 26;
- AGP built-in Kotlin;
- Firebase BoM 34.18.0;
- google-services Gradle plugin 4.5.0.

## Account-specific files

You must supply:

- `android/app/google-services.json` from your Firebase Android app;
- `QUAKEMESH_API_BASE_URL` and `QUAKEMESH_API_KEY` entries in Android `local.properties` for the controlled HTTPS demo transport.

Both files are gitignored.

## Wrapper limitation of the generated release

The source includes `gradle-wrapper.properties` with Gradle 9.6.0. If `gradle-wrapper.jar`, `gradlew`, or `gradlew.bat` are absent in the release environment, open the project in a current Android Studio or run `gradle wrapper --gradle-version 9.6.0` once on the development PC. This is a packaging-environment limitation, not a claim that an APK was built here.

## Emulator

Use Android Studio’s emulator/Virtual Sensors controls for accelerometer/location testing. Synthetic experiment truth should remain in the Python simulator; Android emulator sensor injection is for client-path validation only.
