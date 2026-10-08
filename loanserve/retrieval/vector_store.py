from pathlib import Path
import json
import chromadb
from sentence_transformers import SentenceTransformer

from config.constants import POLICY_CHUNK_CHARACTERS, POLICY_STORE_PATH
from loanserve.retrieval.chunking import chunk_documents
from loanserve.retrieval.document_loader import load_policy_documents


def load_embedder():
    """Loads SentenceTransformer all-MiniLM-L6-v2 embedding model."""
    return SentenceTransformer("all-MiniLM-L6-v2")


def open_policy_store(store_path):
    """Opens persistent ChromaDB policy documents collection with cosine distance metric."""
    client = chromadb.PersistentClient(path=str(store_path))
    collection = client.get_or_create_collection(
        name="policy_documents",
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def describe_chunks(chunks, manifest_path):
    """Enriches policy chunks with product, category, date, and document metadata."""
    manifest_data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    manifest = {entry["document_id"]: entry for entry in manifest_data}

    descriptions = []
    for chunk in chunks:
        doc_id = chunk["document_id"]
        entry = manifest.get(doc_id, {})
        descriptions.append(
            {
                "product_type": entry.get("product_type", "all"),
                "category": entry.get("category", "general"),
                "effective_date": entry.get("effective_date", "2025-01-01"),
                "document_id": doc_id,
                "heading": chunk["heading"],
            }
        )
    return descriptions


def build_policy_store(documents_dir, manifest_path, store_path):
    """Builds and populates the ChromaDB policy store from PDF documents."""
    docs = load_policy_documents(documents_dir)
    chunks = chunk_documents(docs, POLICY_CHUNK_CHARACTERS)
    descriptions = describe_chunks(chunks, manifest_path)
    embedder = load_embedder()

    client = chromadb.PersistentClient(path=str(store_path))
    try:
        client.delete_collection(name="policy_documents")
    except Exception:
        pass
    collection = client.create_collection(
        name="policy_documents",
        metadata={"hnsw:space": "cosine"},
    )

    texts = [c["text"] for c in chunks]
    embeddings = embedder.encode(texts, normalize_embeddings=True).tolist()
    ids = [c["chunk_id"] for c in chunks]

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=descriptions,
    )

    return collection.count()


def search_policy(collection, question, embedder, how_many=3):
    """Performs semantic cosine search across policy chunks."""
    query_vec = embedder.encode([question], normalize_embeddings=True).tolist()
    results = collection.query(
        query_embeddings=query_vec,
        n_results=how_many,
    )

    items = []
    if results and "ids" in results and results["ids"]:
        num_found = len(results["ids"][0])
        for i in range(num_found):
            items.append(
                {
                    "chunk_id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "heading": results["metadatas"][0][i]["heading"],
                    "document_id": results["metadatas"][0][i]["document_id"],
                    "distance": results["distances"][0][i],
                }
            )
    return items


if __name__ == "__main__":
    docs_dir = "data/policy_documents"
    manifest = "data/policy_documents_manifest.json"
    store = "database/policy_store"

    count = build_policy_store(docs_dir, manifest, store)
    print(f"policy store built with {count} chunks")
