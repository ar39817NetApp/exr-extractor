.PHONY: help run logs stop clean test

# Variables
IMAGE_NAME = exr-extractor
IMAGE_TAG = latest
CONTAINER_NAME = exr-extractor
PORT = 50051
DATA_DIR = $(shell pwd)/data

help:
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║          EXR Extraction Service - Port $(PORT)              ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Commands:"
	@echo "  make run     - Build and start service in Docker"
	@echo "  make logs    - View container logs"
	@echo "  make stop    - Stop and remove container"
	@echo "  make clean   - Stop container and remove image"
	@echo "  make test    - Run test (requires container running)"
	@echo ""
	@echo "Test Usage:"
	@echo "  make test INPUT=<input.exr> OUTPUT=<output.png>"
	@echo ""
	@echo "Example:"
	@echo "  make test INPUT=data/input/CrissyField.exr OUTPUT=data/output/CrissyField.png"
	@echo ""
	@echo "Service Info:"
	@echo "  Port: $(PORT)"
	@echo "  Container: $(CONTAINER_NAME)"
	@echo ""

run:
	@echo "Building and starting EXR Extractor service..."
	@docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .
	@docker rm -f $(CONTAINER_NAME) 2>/dev/null || true
	@docker run -d \
		-p $(PORT):$(PORT) \
		-v $(DATA_DIR):/data \
		--name $(CONTAINER_NAME) \
		--restart unless-stopped \
		$(IMAGE_NAME):$(IMAGE_TAG)
	@echo ""
	@echo "✓ Service started successfully"
	@echo "  Endpoint: localhost:$(PORT)"
	@echo "  View logs: make logs"

logs:
	@docker logs -f $(CONTAINER_NAME)

stop:
	@echo "Stopping container..."
	@docker stop $(CONTAINER_NAME) 2>/dev/null || true
	@docker rm $(CONTAINER_NAME) 2>/dev/null || true
	@echo "✓ Container stopped and removed"

clean:
	@echo "Cleaning up..."
	@docker stop $(CONTAINER_NAME) 2>/dev/null || true
	@docker rm $(CONTAINER_NAME) 2>/dev/null || true
	@docker rmi $(IMAGE_NAME):$(IMAGE_TAG) 2>/dev/null || true
	@echo "✓ Cleanup complete"

test:
	@echo "Testing EXR Extractor service..."
	@if ! docker ps --format '{{.Names}}' | grep -q "^$(CONTAINER_NAME)$$"; then \
		echo "Error: Container not running. Start with: make run"; \
		exit 1; \
	fi
	@echo ""
	@echo "Usage: make test INPUT=<exr_file> OUTPUT=<png_file>"
	@echo ""
	@echo "Example:"
	@echo "  make test INPUT=data/input/CrissyField.exr OUTPUT=data/output/CrissyField.png"
	@echo ""
	@if [ -n "$(INPUT)" ] && [ -n "$(OUTPUT)" ]; then \
		echo "Processing: $(INPUT) -> $(OUTPUT)"; \
		mkdir -p "$$(dirname $(OUTPUT))"; \
		CONTAINER_INPUT=$$(echo "$(INPUT)" | sed 's|^data/|/data/|'); \
		CONTAINER_OUTPUT=$$(echo "$(OUTPUT)" | sed 's|^data/|/data/|'); \
		docker exec $(CONTAINER_NAME) python -m client.client "$$CONTAINER_INPUT" "$$CONTAINER_OUTPUT"; \
		echo ""; \
		echo "✓ Test completed. Check output at: $(OUTPUT)"; \
	fi
