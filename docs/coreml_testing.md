# Core ML test backend (macOS)

The optional backend converts the existing trained `models/freediver_s.pt`; it does not train or replace its architecture. BoTSORT, normalized TrackingResult, prediction, smoothing and servo controls stay unchanged.

Use Python 3.12 with native coremltools wheels. Python 3.14 source-only coremltools installations lack the native inference binding. The isolated `.venv-coreml` runtime keeps the original `.venv` available.

```sh
.venv-coreml/bin/python scripts/export_coreml.py
```

The export uses a fixed 640 input, batch 1, FP16 and no embedded NMS. Ultralytics does postprocessing and tracking on CPU. Both tracker modes use the same fixed Core ML input for this experiment.

Set the tracking configuration:

```yaml
tracking:
  inference_backend: coreml
  model_path: models/freediver_s.pt
  coreml_model_path: models/freediver_s.mlpackage
```

Launch from the repository root:

```sh
.venv-coreml/bin/python -m deepsight_host.app
```

The status identifies `Core ML (ALL)`. ALL allows macOS to choose CPU, GPU and Neural Engine; it is not proof that every operation runs on Neural Engine. Core ML initialization errors fail explicitly instead of presenting synthetic tracking as successful inference.

Rollback: set `inference_backend: auto` and launch using the original `.venv/bin/python -m deepsight_host.app`. The original `.pt` file is retained. Close the current Host before starting another instance.
