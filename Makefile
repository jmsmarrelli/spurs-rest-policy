PY := python3

.PHONY: all build rest clean site

all: build rest

build:
	$(PY) src/run_01_build.py

rest:
	$(PY) src/run_02_rest.py

# Regenerate the GitHub Pages page from README.md. Needs `pip install markdown`.
site:
	$(PY) tools/site.py

clean:
	rm -f figures/*.png output/*.csv data/processed/*
