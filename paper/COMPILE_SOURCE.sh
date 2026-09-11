#!/bin/sh
set -eu

# The archive argument binds this check to the release under verification.
test -f "$1"
: "${TMPDIR:?TMPDIR must be set by the release verifier}"
compile_dir=$(mktemp -d "${TMPDIR%/}/claim-indexed-arxiv-compile.XXXXXX")
trap 'rm -rf "$compile_dir"' EXIT HUP INT TERM
printf 'compile_dir=%s\n' "$compile_dir"
cp main.bbl "$compile_dir/main.bbl"
pdflatex -halt-on-error -interaction=nonstopmode -output-directory="$compile_dir" main.tex
pdflatex -halt-on-error -interaction=nonstopmode -output-directory="$compile_dir" main.tex
pdflatex -halt-on-error -interaction=nonstopmode -output-directory="$compile_dir" main.tex
test -s "$compile_dir/main.pdf"
