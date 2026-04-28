# =============================================================================
# Author:  Yash Daniel Ingle
# Email:   yashingle1207@gmail.com
# GitHub:  github.com/yashingle1207
# Project: Video Codec Validation Lab
# File:    Makefile
# Purpose: Build, test, run, and clean the validation lab from one entry point.
# =============================================================================
#
# Targets:
#   help           Print available targets
#   build          Compile the C++ yuv_frame_validator binary
#   test           Run the full pytest suite
#   generate       Generate synthetic YUV test clips
#   run            Run the full validation pipeline
#   validate       Build and run tests
#   clean          Remove build artifacts and cached files

CXX      := g++
CXXFLAGS := -std=c++14 -O2 -Wall -Wextra
# No external link dependencies - SHA-256 is self-contained.
LDFLAGS  :=

SRC_CPP  := src/yuv_frame_validator.cpp
BIN      := build/yuv_frame_validator$(if $(OS),.exe,)

.PHONY: help build test generate generate-clips run validate full-run clean

help:
	@echo "Video Codec Validation Lab targets:"
	@echo "  make build          Compile the C++ YUV frame validator"
	@echo "  make test           Run pytest"
	@echo "  make generate       Generate synthetic YUV clips"
	@echo "  make run            Run the validation pipeline"
	@echo "  make validate       Build and run tests"
	@echo "  make clean          Remove build artifacts and generated outputs"

build:
	mkdir -p build
	$(CXX) $(CXXFLAGS) -o $(BIN) $(SRC_CPP) $(LDFLAGS)
	@echo "Built: $(BIN)"

test:
	python -m pytest tests/ -v --tb=short

generate generate-clips:
	bash scripts/generate_synthetic_clips.sh

run full-run: generate-clips
	bash scripts/run_validation_pipeline.sh

validate: build test

clean:
	rm -f build/yuv_frame_validator build/yuv_frame_validator.exe
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf outputs/encoded/* outputs/decoded/* outputs/metrics/* \
	       outputs/plots/* outputs/reports/*
	touch outputs/encoded/.gitkeep outputs/decoded/.gitkeep outputs/metrics/.gitkeep \
	      outputs/plots/.gitkeep outputs/reports/.gitkeep
	@echo "Clean complete"
