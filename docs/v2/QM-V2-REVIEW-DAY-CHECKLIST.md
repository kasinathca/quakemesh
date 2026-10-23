# QuakeMesh V2 review-day checklist

Print this page or keep it open during the demonstration.

## Before the audience arrives

- [ ] Windows laptop is connected to power and the internet.
- [ ] Repository is on `main` or `codex/android-v2-research-notifications` with no uncommitted work.
- [ ] `aws sts get-caller-identity --profile quakemesh-demo --region ap-south-1` returns account `101541767123` and a non-root identity.
- [ ] `PREPARE_QUAKEMESH_REVIEW.cmd` ends with `QUAKEMESH REVIEW PREPARATION PASSED`.
- [ ] Firebase file exists at `android/app/google-services.json`; no token or credential is displayed or committed.
- [ ] Phone has internet, sufficient charge, location enabled, and notifications enabled.
- [ ] USB cable and ADB are available for the initial installation only.
- [ ] Previous `STATUS_QUAKEMESH_REVIEW.cmd` shows no unexpected owned stack.

## Start

- [ ] Connect and unlock exactly one phone.
- [ ] `adb devices -l` shows one `device`, not `unauthorized` or `offline`.
- [ ] Run `START_QUAKEMESH_REVIEW.cmd`.
- [ ] Confirm `QUAKEMESH REVIEW ENVIRONMENT READY`.
- [ ] Confirm smoke and distributed warm-up both say `PASS`.
- [ ] Open Local V2 at `http://127.0.0.1:8080`.
- [ ] Open AWS V2 at `http://127.0.0.1:8081`.
- [ ] Confirm both dashboard headers show `connected` and the expected environment.

## Phone

- [ ] Open QuakeMesh and grant location/notification permissions.
- [ ] Simulated-drill alerts show `OPTED IN`.
- [ ] Full-screen permission shows `Allowed`, or note that urgent heads-up fallback will be used.
- [ ] Tap **Start monitoring**.
- [ ] API state becomes `Connected`.
- [ ] Latest heartbeat is current.
- [ ] Location state includes a current H3 cell.
- [ ] AWS **Devices** shows the physical device, online state, H3 cell, and enabled drill opt-in.
- [ ] Disconnect USB.
- [ ] `adb devices -l` is empty before starting the review scenario.

## Explain before triggering

- [ ] State that this is a labeled simulated earthquake drill, not an official warning.
- [ ] Explain that the physical phone is the geographic reference and alert recipient.
- [ ] Explain that separately identified virtual phones provide all synthetic evidence.
- [ ] Explain four-device, three-cell, time-window, and H3-coherence gates.
- [ ] Explain that Detection Footprint is contributing cells and Warning Frontier is a targeting ring, not a seismic wavefront.

## Positive wireless demonstration

- [ ] AWS **Scenario Lab** → **Distributed corroboration** → `devices = 25` → **Start**.
- [ ] Run changes `QUEUED` → `RUNNING` → `COMPLETED`.
- [ ] Expected/observed result is `CONFIRMATION`.
- [ ] Gate evaluation shows device diversity, spatial diversity, recency, and coherence.
- [ ] Live Map shows virtual devices, physical reference phone, Detection Footprint, and Warning Frontier.
- [ ] Phone receives the notification without USB.
- [ ] If unlocked: heads-up notification appears; tap it to open the full warning.
- [ ] If locked and permission allowed: full warning appears over the keyguard.
- [ ] Audible alert and spoken warning are heard.
- [ ] Tap **STOP ALERT SOUND** and verify attention output stops.
- [ ] Tap **ACKNOWLEDGE / DISMISS**.
- [ ] Dashboard **Alerts** reports `ACKNOWLEDGED` for the physical phone.

## Negative and degraded cases

- [ ] **Isolated disturbance** → `NO_CONFIRMATION`.
- [ ] **Same-cell cluster** → `NO_CONFIRMATION` because cell diversity fails.
- [ ] **False-positive demonstration** → `NO_CONFIRMATION` because ordinary/uncorrelated motion does not satisfy quorum.
- [ ] **Degraded network** → `CONDITIONAL`; interpret the observed result using surviving evidence, loss, and jitter.
- [ ] Do not claim a notification for a negative run.

## Academic evidence

- [ ] Show historical baseline separately: 48 trials, TP=24, TN=24, FP=0, FN=0, mean confirmation latency 513.75 ms.
- [ ] Show challenging benchmark separately: 320 trials, TP=86, TN=151, FP=25, FN=58, F1=0.6745.
- [ ] State that these are controlled software-simulation results, not real-world earthquake accuracy.
- [ ] State that UCI HAR is a single-device human-activity gate evaluation, not an event false-alarm rate.
- [ ] Mention limitations: no magnitude/epicentre estimate, no life-safety validation, limited handset coverage, and automatic expiry not relied upon.

## Stop and verify

- [ ] Run `STOP_QUAKEMESH_REVIEW.cmd`, even if START or the demonstration failed.
- [ ] Wait for `CLEAN`.
- [ ] Run `STATUS_QUAKEMESH_REVIEW.cmd` if the result is unclear.
- [ ] Confirm ports 8000, 8080, and 8081 are stopped.
- [ ] Confirm active owned QuakeMesh stacks = 0.
- [ ] Confirm review state is absent and Android build target is restored.
- [ ] Preserve ignored screenshots/evidence; do not run `git clean -fdx`.
- [ ] Record any `INCOMPLETE` result and investigate only through the exact-session guarded workflow.
