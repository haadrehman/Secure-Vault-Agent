import os
import sqlite3
import chromadb
from chromadb.utils import embedding_functions

# A lightweight local model (e.g., all-MiniLM-L6-v2)
default_ef = embedding_functions.DefaultEmbeddingFunction()

class VaultDatabase:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.db_path = os.path.join(workspace_dir, "vault_state.db")
        self.chroma_dir = os.path.join(workspace_dir, "chroma_db")
        
        # Initialize SQLite for sessions/maps
        self._init_sqlite()
        
        # Initialize ChromaDB for vectors
        self.chroma_client = chromadb.PersistentClient(path=self.chroma_dir)
        self.collection = self.chroma_client.get_or_create_collection(
            name="vault_documents",
            embedding_function=default_ef
        )

    def _init_sqlite(self):
        # Fallback gracefully to sqlite3 (sqlcipher not standard without specialized setup)
        try:
            from pysqlcipher3 import dbapi2 as sqlite
            self.sqlite = sqlite
            # We would set a PRAGMA key here in a real scenario
        except ImportError:
            self.sqlite = sqlite3
            
        self.conn = self.sqlite.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_sessions (
                session_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS anonymization_maps (
                session_id TEXT,
                token TEXT,
                original_value TEXT,
                FOREIGN KEY(session_id) REFERENCES conversation_sessions(session_id)
            )
        ''')
        
        self.conn.commit()

    def add_document_chunks(self, doc_id: str, chunks: list[str], metadata: dict):
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        metadatas = [metadata for _ in chunks]
        self.collection.add(documents=chunks, ids=ids, metadatas=metadatas)
        
    def query_documents(self, query: str, n_results: int = 5) -> list[str]:
        results = self.collection.query(query_texts=[query], n_results=n_results)
        if results['documents'] and len(results['documents']) > 0:
            return results['documents'][0]
        return []

    def get_document_names(self) -> list[str]:
        # Retrieve all documents to extract unique metadata filenames safely
        results = self.collection.get(include=['metadatas'])
        names = set()
        if results['metadatas']:
            for m in results['metadatas']:
                if m and 'filename' in m:
                    names.add(m['filename'])
        return list(names)
