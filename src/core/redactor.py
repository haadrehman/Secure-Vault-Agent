import collections
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

class PIIRedactor:
    def __init__(self):
        """Initializes Presidio Analyzer and Anonymizer engines locally."""
        # Initialize engines. This runs entirely locally on CPU.
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
        # Entities we want to redact as per PRD
        self.entities = [
            "PERSON", "US_SSN", "CREDIT_CARD", "EMAIL_ADDRESS", "PHONE_NUMBER", "MONEY"
        ]

    def redact_text(self, text: str) -> tuple[str, dict]:
        """
        Analyzes text for PII entities. Replaces them with sequential tokens.
        Returns:
            anonymized_text: str (e.g., "The client [PERSON_1] owes [MONEY_1]")
            token_map: dict (e.g., {"[PERSON_1]": "John Doe", "[MONEY_1]": "$5,000"})
        """
        from src.core.telemetry import get_tracer
        tracer = get_tracer()
        with tracer.start_as_current_span("local_redact") as span:
            # Analyze the text
            results = self.analyzer.analyze(text=text, entities=self.entities, language="en")
            
            # Sort results descending by start index to avoid index shifting when replacing
            results = sorted(results, key=lambda x: x.start, reverse=True)
            
            counters = collections.defaultdict(int)
            token_map = {}
            anonymized_text = text
            
            # Refined token assignment (forward pass)
            results_forward = sorted(results, key=lambda x: x.start)
            entity_to_token = {} # maps specific result object (by id/ref) to token
            
            for result in results_forward:
                entity_type = result.entity_type
                counters[entity_type] += 1
                token_name = f"[{entity_type}_{counters[entity_type]}]"
                # We use (result.start, result.end, result.entity_type) as a unique key for this match
                entity_to_token[(result.start, result.end, result.entity_type)] = token_name
                
                original_value = text[result.start:result.end]
                token_map[token_name] = original_value
                
            # Backward replacement pass
            for result in results:
                token_name = entity_to_token[(result.start, result.end, result.entity_type)]
                anonymized_text = anonymized_text[:result.start] + token_name + anonymized_text[result.end:]
                
            span.set_attribute("redacted_entity_count", len(token_map))
            
            return anonymized_text, token_map

    def restore_text(self, redacted_text: str, token_map: dict) -> str:
        """ Replaces placeholder tokens back with real data from the map. """
        restored_text = redacted_text
        for token, original_value in token_map.items():
            restored_text = restored_text.replace(token, original_value)
        return restored_text
