import chromadb
import time
import uuid

class RAGEngine:
    def __init__(self):
        self.client = chromadb.PersistentClient(path="./db/chroma_storage")
        self.collection = self.client.get_or_create_collection(
            name="support_docs"
        )
        
        self.chat_collection = self.client.get_or_create_collection(
            name="chat_history"
        )

    def add_document(self, content: str, title: str = None, metadata_dict: dict = None) -> str:
        """Adds a single document with metadata to the vector storage."""
        doc_id = f"doc_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        title = title or (content[:30] + "..." if len(content) > 30 else content)
        
        meta = {
            "title": title,
            "timestamp": time.time(),
            "content_length": len(content)
        }
        if metadata_dict:
            meta.update(metadata_dict)
        
        self.collection.add(
            documents=[content],
            metadatas=[meta],
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
            docs = []
            if results and results.get("documents") and len(results["documents"]) > 0:
                for i in range(len(results["documents"][0])):
                    docs.append({
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") else {}
                    })
            return docs
        except Exception:
            return []

    def get_chat_history(self, session_id: str) -> list:
        try:
            results = self.chat_collection.get(
                where={"session_id": session_id}
            )
            messages = []
            if results and results.get("ids"):
                for i in range(len(results["ids"])):
                    metadata = results["metadatas"][i]
                    messages.append({
                        "role": metadata["role"],
                        "content": results["documents"][i],
                        "timestamp": metadata["timestamp"]
                    })
            # Sort chronologically by timestamp
            messages.sort(key=lambda x: x["timestamp"])
            return messages
        except Exception as e:
            print(f"Error getting chat history: {e}")
            return []

    def add_chat_message(self, session_id: str, role: str, content: str):
        try:
            message_id = f"msg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:4]}"
            self.chat_collection.add(
                documents=[content],
                metadatas=[{
                    "session_id": session_id,
                    "role": role,
                    "timestamp": time.time()
                }],
                ids=[message_id]
            )
        except Exception as e:
            print(f"Error adding chat message: {e}")

    def clear_chat_history(self, session_id: str):
        try:
            self.chat_collection.delete(where={"session_id": session_id})
        except Exception as e:
            print(f"Error clearing chat history: {e}")

    def get_all_sessions(self) -> list:
        try:
            results = self.chat_collection.get()
            sessions = {}
            if results and results.get("metadatas"):
                for i in range(len(results["metadatas"])):
                    meta = results["metadatas"][i]
                    doc = results["documents"][i]
                    sess_id = meta["session_id"]
                    role = meta["role"]
                    timestamp = meta["timestamp"]
                    
                    if sess_id not in sessions:
                        sessions[sess_id] = {
                            "session_id": sess_id,
                            "first_message": "",
                            "timestamp": timestamp
                        }
                    # We want the first message sent by the User as the title
                    if role == "User" and (not sessions[sess_id]["first_message"] or timestamp < sessions[sess_id]["timestamp"]):
                        sessions[sess_id]["first_message"] = doc
                        sessions[sess_id]["timestamp"] = timestamp
            
            # Convert to list and sort by timestamp descending (newest first)
            sess_list = list(sessions.values())
            sess_list.sort(key=lambda x: x["timestamp"], reverse=True)
            return sess_list
        except Exception as e:
            print(f"Error getting all sessions: {e}")
            return []