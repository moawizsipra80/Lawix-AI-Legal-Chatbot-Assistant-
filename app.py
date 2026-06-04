from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request

try:
    import chromadb
except ImportError:  # pragma: no cover
    chromadb = None


DEFAULT_KNOWLEDGE = [
    {
        "id": "return_policy",
        "text": "You can return most items within 30 days of purchase with proof of payment.",
    },
    {
        "id": "shipping_time",
        "text": "Standard shipping usually takes 3 to 5 business days.",
    },
    {
        "id": "support_contact",
        "text": "For urgent help, contact support@yourcompany.com anytime.",
    },
]


def _embed_text(text: str) -> list[float]:
    vector = [0.0] * 26
    for char in text.lower():
        if "a" <= char <= "z":
            vector[ord(char) - ord("a")] += 1.0
    return vector


class KnowledgeBase:
    def __init__(self, storage_path: Path, collection_name: str = "customer_support") -> None:
        self._collection = None
        if chromadb is None:
            return

        client = chromadb.PersistentClient(path=str(storage_path))
        self._collection = client.get_or_create_collection(name=collection_name, embedding_function=None)
        self._seed_if_empty()

    def _seed_if_empty(self) -> None:
        if self._collection is None:
            return
        if self._collection.count() > 0:
            return

        self._collection.add(
            ids=[item["id"] for item in DEFAULT_KNOWLEDGE],
            documents=[item["text"] for item in DEFAULT_KNOWLEDGE],
            embeddings=[_embed_text(item["text"]) for item in DEFAULT_KNOWLEDGE],
            metadatas=[{"source": "default"} for _ in DEFAULT_KNOWLEDGE],
        )

    def search(self, query: str) -> str | None:
        if not query.strip():
            return None

        query_l = query.lower()
        if "return" in query_l:
            return DEFAULT_KNOWLEDGE[0]["text"]
        if "ship" in query_l or "deliver" in query_l:
            return DEFAULT_KNOWLEDGE[1]["text"]
        if "support" in query_l or "contact" in query_l or "help" in query_l:
            return DEFAULT_KNOWLEDGE[2]["text"]

        if self._collection is not None:
            result = self._collection.query(
                query_embeddings=[_embed_text(query)],
                n_results=1,
                include=["documents", "distances"],
            )
            docs = result.get("documents")
            distances = result.get("distances")
            if docs and docs[0] and distances and distances[0] and distances[0][0] <= 50:
                return docs[0][0]

        # Lightweight fallback when ChromaDB is unavailable.
        for item in DEFAULT_KNOWLEDGE:
            if any(token in item["id"] for token in query_l.split()):
                return item["text"]
        return None


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="")
    kb = KnowledgeBase(storage_path=Path("./chroma_data"))

    @app.get("/")
    def home() -> tuple[str, int]:
        return app.send_static_file("index.html"), 200

    @app.get("/api/health")
    def health() -> tuple[dict[str, str], int]:
        return {"status": "ok"}, 200

    @app.post("/api/chat")
    def chat() -> tuple[dict[str, str], int]:
        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message", "")).strip()
        if not message:
            return jsonify({"error": "message is required"}), 400

        answer = kb.search(message)
        if answer is None:
            answer = (
                "Thanks for your question. I can help with shipping, returns, and support "
                "contact details right now."
            )

        return jsonify({"reply": answer}), 200

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
