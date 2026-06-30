import sys
from unittest.mock import MagicMock

# Mock presidio_analyzer
mock_presidio_analyzer = MagicMock()

class MockAnalyzerEngine:
    def analyze(self, text, entities, language):
        results = []
        if "John Doe" in text:
            m = MagicMock()
            m.start = text.find("John Doe")
            m.end = m.start + len("John Doe")
            m.entity_type = "PERSON"
            results.append(m)
        if "123-456-7890" in text:
            m = MagicMock()
            m.start = text.find("123-456-7890")
            m.end = m.start + len("123-456-7890")
            m.entity_type = "US_SSN"
            results.append(m)
        if "4111-1111-1111-1111" in text:
            m = MagicMock()
            m.start = text.find("4111-1111-1111-1111")
            m.end = m.start + len("4111-1111-1111-1111")
            m.entity_type = "CREDIT_CARD"
            results.append(m)
        return results

mock_presidio_analyzer.AnalyzerEngine = MockAnalyzerEngine
sys.modules['presidio_analyzer'] = mock_presidio_analyzer

mock_presidio_anonymizer = MagicMock()
sys.modules['presidio_anonymizer'] = mock_presidio_anonymizer

# We also need to mock chromadb.PersistentClient to avoid hangs
mock_chroma = MagicMock()
sys.modules['chromadb'] = mock_chroma
sys.modules['chromadb.utils'] = MagicMock()
sys.modules['chromadb.config'] = MagicMock()
