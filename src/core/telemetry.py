from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

# Initialize OpenTelemetry with a console span exporter for trajectory tracking
provider = TracerProvider()
processor = SimpleSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)

# Set the global tracer provider
trace.set_tracer_provider(provider)

# Provide a helper to get the tracer for this module
tracer = trace.get_tracer("secure-vault-agent")

def get_tracer():
    return tracer
