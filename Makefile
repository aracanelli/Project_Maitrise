PY = .venv/Scripts/python.exe

.PHONY: test pipeline evaluate manifest

test:
	$(PY) -m pytest -q tests

# all pipeline stages in order; pass --from/--to/--overwrite through PIPELINE_ARGS
pipeline:
	$(PY) -m scripts.run_pipeline $(PIPELINE_ARGS)

evaluate:
	$(PY) -m scripts.evaluate --setting R4 --lang both
	$(PY) -m scripts.evaluate --setting R1 --lang both
	$(PY) -m scripts.evaluate --setting R10 --lang both

# run manifest (data/results/run_manifest.json) and requirements-lock.txt
manifest:
	$(PY) -m scripts.write_manifest
