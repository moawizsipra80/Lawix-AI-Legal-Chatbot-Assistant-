import chromadb
import time
import uuid

class RAGEngine:
    def __init__(self):
        # Store Chroma files inside db/chroma_storage
        self.client = chromadb.PersistentClient(path="./db/chroma_storage")
        self.collection = self.client.get_or_create_collection(
            name="support_docs"
        )
        # Session memory for chat context (key: session_id, value: list of message dicts)
        self.memory = {}

    def add_document(self, content: str, title: str = None) -> str:
        """Adds a single document with metadata to the vector storage."""
        doc_id = f"doc_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        title = title or (content[:30] + "..." if len(content) > 30 else content)
        
        self.collection.add(
            documents=[content],
            metadatas=[{
                "title": title,
                "timestamp": time.time(),
                "content_length": len(content)
            }],
            ids=[doc_id]
        )
        return doc_id

    def add_documents(self, docs: list):
        """Batch adds simple string documents (used for initialization/demos)."""
        for doc in docs:
            # Check if this document already exists to prevent duplicate demo items
            existing = self.get_all_documents()
            if not any(d["content"] == doc for d in existing):
                self.add_document(doc)

    def get_all_documents(self) -> list:
        """Retrieves all documents and their metadata from the collection."""
        try:
            results = self.collection.get()
            docs = []
            if results and results.get("ids"):
                for i in range(len(results["ids"])):
                    metadata = results["metadatas"][i] if results.get("metadatas") else {}
                    docs.append({
                        "id": results["ids"][i],
                        "content": results["documents"][i],
                        "title": metadata.get("title", "Untitled Document"),
                        "timestamp": metadata.get("timestamp", time.time())
                    })
            # Sort by timestamp descending
            docs.sort(key=lambda x: x["timestamp"], reverse=True)
            return docs
        except Exception:
            return []

    def delete_document(self, doc_id: str) -> bool:
        """Deletes a document from the collection by ID."""
        try:
            self.collection.delete(ids=[doc_id])
            return True
        except Exception:
            return False

    def search(self, query: str, n_results: int = 3) -> list:
        """Queries the vector database for matching knowledge context chunks."""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            # Flatten or format documents list
            if results and results.get("documents") and len(results["documents"]) > 0:
                return results["documents"][0]
            return []
        except Exception:
            return []

    # Simple session management for conversation memory
    def get_chat_history(self, session_id: str) -> list:
        if session_id not in self.memory:
            self.memory[session_id] = []
        return self.memory[session_id]

    def add_chat_message(self, session_id: str, role: str, content: str):
        if session_id not in self.memory:
            self.memory[session_id] = []
        self.memory[session_id].append({"role": role, "content": content})
        # Keep only the last 10 turns to avoid context overflow
        if len(self.memory[session_id]) > 20:
            self.memory[session_id] = self.memory[session_id][-20:]

    def clear_chat_history(self, session_id: str):
        self.memory[session_id] = []