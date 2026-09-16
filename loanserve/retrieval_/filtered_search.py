import re
from loanserve.retrieval.vector_store import search_policy


def product_in_question(question):
    """Identifies loan product referenced in question text, or 'all' if none."""
    if not isinstance(question, str):
        return "all"

    q = question.lower()
    if re.search(r"\b(?:home|housing|mortgage|property)\b", q):
        return "home"
    if re.search(r"\b(?:vehicle|car|auto|two-wheeler|bike)\b", q):
        return "vehicle"
    if re.search(r"\b(?:gold|ornaments|jewellery|purity)\b", q):
        return "gold"
    if re.search(r"\b(?:personal)\b", q):
        return "personal"

    return "all"


def policy_filter(product_type):
    """Builds ChromaDB metadata query filter for specified product and universal rules."""
    prod = str(product_type).strip().lower()
    if prod == "all":
        return {"product_type": "all"}
    return {"product_type": {"$in": [prod, "all"]}}


def filtered_search(collection, question, embedder, how_many=3):
    """Executes metadata-filtered cosine search over policy collection."""
    prod = product_in_question(question)
    where_filter = policy_filter(prod)
    query_vec = embedder.encode([question], normalize_embeddings=True).tolist()

    results = collection.query(
        query_embeddings=query_vec,
        n_results=how_many,
        where=where_filter,
    )

    items = []
    if results and "ids" in results and results["ids"]:
        for i in range(len(results["ids"][0])):
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
