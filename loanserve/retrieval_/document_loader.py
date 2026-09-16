from pathlib import Path
from pypdf import PdfReader


def load_policy_documents(directory_path):
    """Loads all PDF policy documents from directory and extracts complete text."""
    dir_p = Path(directory_path)
    documents = []

    for pdf_file in sorted(dir_p.glob("*.pdf")):
        doc_id = pdf_file.stem
        reader = PdfReader(str(pdf_file))
        pages_text = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages_text.append(t)

        full_text = "\n".join(pages_text)
        documents.append(
            {
                "document_id": doc_id,
                "text": full_text,
            }
        )

    return documents


if __name__ == "__main__":
    docs = load_policy_documents("data/policy_documents")
    print(f"loaded {len(docs)} policy documents")
