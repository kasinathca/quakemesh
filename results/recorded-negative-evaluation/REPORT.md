# Recorded smartphone negative-case evaluation

Source: UCI Human Activity Recognition Using Smartphones, DOI `10.24432/C54S4K`, CC BY 4.0. Archive SHA-256: `c00b803081a5c797cd5e4b83700a9810b38d53d9d84e01917e090e1fdbc81031`.

This evaluates only the QuakeMesh single-device motion gate on authentic video-labeled everyday smartphone accelerometer windows. It is not event-level spatial-correlation performance and not earthquake accuracy.

The held-out subject partition contained 1000 windows: 469 passed the motion gate and 531 did not. Held-out false-positive window rate was 0.4690 (95% Wilson interval 0.4382–0.5000). “False positive” here means a negative activity window passed the local motion gate; the multi-device H3 correlator would still need independent spatial quorum.

| Activity | Windows | Gate positives | Gate-positive rate |
|---|---:|---:|---:|
| WALKING | 395 | 395 | 1.0000 |
| WALKING_UPSTAIRS | 308 | 308 | 1.0000 |
| WALKING_DOWNSTAIRS | 279 | 279 | 1.0000 |
| SITTING | 313 | 0 | 0.0000 |
| STANDING | 358 | 0 | 0.0000 |
| LAYING | 347 | 4 | 0.0115 |

Data are 50 Hz, 128-sample windows. Source total acceleration in standard-gravity units is multiplied by 9.80665 and processed by production `extract_motion_features` and `passes_motion_gate`. Raw data remain in ignored `artifacts/datasets/` and are not committed.
