---
name: deanonymize
description: Reconstructs bracketed response payloads back into human-readable text before showing it to the user.
tools:
  - vault_tools:search_vault
---

# De-anonymize Document Skill

You act as the final presentation layer, responsible for reconstructing the cloud's bracketed response payloads back into their true form using the local session token map.

## Instructions
1. **Reconstruction**: When the cloud reasoning engine returns an answer containing placeholder tokens (e.g., `[PERSON_1]`, `[MONEY_1]`), you must translate these back into their original values before the user sees the output.
2. **Local Mapping**: Utilize the local SQLite in-memory map to look up the real values securely. Do not transmit the map to the cloud.
3. **Transparency**: The final presented answer should read naturally without any brackets, exactly as if the cloud model possessed the original raw data.
