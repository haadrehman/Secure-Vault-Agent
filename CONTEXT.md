# Secure Coding Standards

## 1. Zero-Leakage Policy
No raw document context or unredacted PII may ever be pushed to the remote repository, logged to consoles, or persisted in unencrypted databases. All components must strictly adhere to the local data boundary defined in the System Architecture.

## 2. Hardcoded Secrets
Absolutely no hardcoded API keys, tokens, or credentials are allowed in the source code. All secrets (like Gemini API keys) must be loaded dynamically via environment variables (`.env`) or secure secret managers.

## 3. Local PII Redaction
All redaction must occur locally using Microsoft Presidio (or an equivalent local engine) before any data is sent to external APIs (e.g., Gemini). The token map must remain in memory or in the local encrypted SQLite database and never be transmitted.

## 4. Input Validation
All file inputs and paths must be validated to prevent directory traversal attacks. Paths must reside strictly within the allowed workspace boundary. Unvalidated `open()` calls are flagged by security scans.

## 5. Package Safety
Any new dependencies must be evaluated for security and safety. Do not introduce arbitrary execution tools without sandbox constraints.
