.PHONY: help build test shell clean example docs

# Default target
help:
	@echo "KUKSA Test Framework v4 - Available targets:"
	@echo "  build       - Build the test framework Docker image"
	@echo "  test        - Run unit tests"
	@echo "  shell       - Start interactive shell in test container"
	@echo "  example     - Run the climate control example"
	@echo "  clean       - Stop and remove containers"
	@echo "  docs        - Generate documentation"

# Build Docker image
build:
	docker-compose -f docker-compose.test.yml build test-runner

# Run unit tests
test: build
	docker-compose -f docker-compose.test.yml run --rm test-runner pytest tests/

# Interactive shell
shell: build
	docker-compose -f docker-compose.test.yml run --rm test-runner /bin/bash

# Run example
example: build
	@echo "Starting KUKSA databroker..."
	docker-compose -f docker-compose.test.yml up -d databroker
	@echo "Waiting for services to start..."
	@sleep 5
	@echo "Running climate control example..."
	docker-compose -f docker-compose.test.yml run --rm test-runner \
		python -m kuksa_test.cli \
		/app/examples/climate_control_test.yaml \
		--kuksa-url databroker:55555 \
		--format console
	@make clean

# Clean up
clean:
	docker-compose -f docker-compose.test.yml down -v

# Generate documentation
docs:
	@echo "Generating API documentation..."
	docker-compose -f docker-compose.test.yml run --rm test-runner \
		python -m pydoc -w kuksa_test