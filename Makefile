.PHONY: help build run stop start logs logs-follow clean test test-stream venv proto install health run-native

# Variables
IMAGE_NAME = exr-extractor
IMAGE_TAG = latest
CONTAINER_NAME = exr-extractor
PORT = 50051
VENV_DIR := .venv
DATA_DIR = $(shell pwd)/data

# Default target
help:
	@echo "EXR Extraction Service - Makefile Commands"
	@echo ""
	@echo "Server:"
	@echo "  make run-native     Run server natively (without Docker)"
	@echo "  make run            Run Docker container with volume mounted"
	@echo ""
	@echo "Docker Commands:"
	@echo "  make build          Build Docker image"
	@echo "  make stop           Stop the container"
	@echo "  make start          Start stopped container"
	@echo "  make logs           View container logs"
	@echo "  make logs-follow    Follow container logs in real-time"
	@echo "  make clean          Stop and remove container"
	@echo ""
	@echo "Testing:"
	@echo "  make health         Check server health"
	@echo "  make test           Run test (unary): <exr_file> <output_png>"
	@echo "  make test-stream    Run test (streaming): <exr_file> <output_png>"
	@echo ""
	@echo "Development:"
	@echo "  make venv           Create Python virtual environment"
	@echo "  make proto          Regenerate gRPC code from proto"
	@echo "  make install        Install Python dependencies locally"

# Native server (without Docker)
run-native:
	@echo "Starting EXR Extractor server on port $(PORT)..."
	$(VENV_DIR)/bin/python -m server.main

# Health check
health:
	@echo "Checking server health at localhost:$(PORT)..."
	$(VENV_DIR)/bin/python -m client.client --health --port=$(PORT)

# Docker commands
build:
	@echo "Building Docker image..."
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

run:
	@echo "Starting container..."
	docker run -d \
		-p $(PORT):$(PORT) \
		-v $(DATA_DIR):/data \
		--name $(CONTAINER_NAME) \
		$(IMAGE_NAME):$(IMAGE_TAG)
	@echo "Container started. Use 'make logs' to view logs."

stop:
	@echo "Stopping container..."
	docker stop $(CONTAINER_NAME)

start:
	@echo "Starting container..."
	docker start $(CONTAINER_NAME)

logs:
	docker logs $(CONTAINER_NAME)

logs-follow:
	docker logs -f $(CONTAINER_NAME)

clean:
	@echo "Removing container..."
	-docker rm -f $(CONTAINER_NAME)

# Test command
# Extract positional arguments for test target
TEST_ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
TEST_EXR := $(word 1,$(TEST_ARGS))
TEST_PNG := $(word 2,$(TEST_ARGS))
test:
	@echo "Testing gRPC service..."
	@if [ -z "$(TEST_EXR)" ]; then \
		echo "ERROR: EXR file path required"; \
		echo "Usage: make test <exr_file> <output_png>"; \
		echo "Example: make test data/input/file.exr data/output/result.png"; \
		exit 1; \
	fi
	@if [ ! -f "$(TEST_EXR)" ]; then \
		echo "ERROR: EXR file not found: $(TEST_EXR)"; \
		exit 1; \
	fi
	@if [ -z "$(TEST_PNG)" ]; then \
		echo "ERROR: Output PNG path required"; \
		echo "Usage: make test <exr_file> <output_png>"; \
		exit 1; \
	fi
	@mkdir -p "$$(dirname "$(TEST_PNG)")"
	$(VENV_DIR)/bin/python -m client.client "$(TEST_EXR)" "$(TEST_PNG)"

# Test command with streaming
test-stream:
	@echo "Testing gRPC service (streaming mode)..."
	@if [ -z "$(TEST_EXR)" ]; then \
		echo "ERROR: EXR file path required"; \
		echo "Usage: make test-stream <exr_file> <output_png>"; \
		exit 1; \
	fi
	@if [ ! -f "$(TEST_EXR)" ]; then \
		echo "ERROR: EXR file not found: $(TEST_EXR)"; \
		exit 1; \
	fi
	@if [ -z "$(TEST_PNG)" ]; then \
		echo "ERROR: Output PNG path required"; \
		exit 1; \
	fi
	@mkdir -p "$$(dirname "$(TEST_PNG)")"
	$(VENV_DIR)/bin/python -m client.client "$(TEST_EXR)" "$(TEST_PNG)" --stream

# Catch-all to prevent "No rule to make target" errors for arguments
$(TEST_ARGS):
	@:

# Development commands
venv:
	@echo "Creating virtual environment..."
	python3 -m venv $(VENV_DIR)
	@echo "Virtual environment created at $(VENV_DIR)"
	@echo "Activate it with: source $(VENV_DIR)/bin/activate"

proto:
	@echo "Regenerating gRPC code from proto..."
	python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/extractor.proto

install:
	@echo "Installing Python dependencies..."
	$(VENV_DIR)/bin/pip install -r requirements.txt
