.PHONY: all derive check paper clean

all: check paper

derive:
	python3 scripts/build_derived.py

check:
	python3 scripts/build_derived.py --check-only

paper: derive
	mkdir -p build
	latexmk -pdf -outdir=build main.tex
	cp build/main.pdf paper.pdf

clean:
	latexmk -C -outdir=build main.tex || true
	rm -f paper.pdf
