---
name: ingest_doc
description: Ingests a new document into the Sovereign Vault. Trigger this when the user asks to add, index, or ingest a file.
tools:
  - vault_tools:ingest_document
---

# Ingest Document Skill

You are responsible for safely ingesting new documents into the local Sovereign Vault.

## Instructions
1. **Validate the File Path**: Before executing the ingestion tool, verify that the provided path is absolute and falls within the authorized workspace boundary. Do not attempt to read files from `/tmp`, `/etc`, or outside the designated project folder.
2. **Execute Ingestion**: Call the `vault_tools:ingest_document` tool with the validated path.
3. **Handle Errors**: If the tool returns a security violation or file not found error, report this to the user immediately without retrying.
4. **Confirmation**: Once successful, confirm to the user that the file has been chunked, vectorized, and stored securely in the local ChromaDB index without leaving the host machine.
