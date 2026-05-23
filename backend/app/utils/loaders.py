"""Document loader registry.

Maps file extension -> loader function. Adding a new file type requires:
  1. Implement `load_<ext>(path) -> str`
  2. Register it in `LOADERS`

Loaders return a single concatenated string (chunking happens downstream).
"""

from langchain_community.document_loaders import (
    Docx2txtLoader,
    PyPDFLoader,
    TextLoader,
)


def _join_documents(docs) -> str:
    """LangChain loaders return a list of Document objects; concatenate text."""
    return "\n\n".join(doc.page_content for doc in docs).strip()


def load_pdf(path: str) -> str:
    return _join_documents(PyPDFLoader(path).load())


def load_docx(path: str) -> str:
    return _join_documents(Docx2txtLoader(path).load())


def load_txt(path: str) -> str:
    return _join_documents(
        TextLoader(path, encoding="utf-8", autodetect_encoding=True).load()
    )


# Extension (lowercase, with leading dot) -> loader callable
LOADERS = {
    ".pdf": load_pdf,
    ".docx": load_docx,
    ".txt": load_txt,
}


def get_loader(extension: str):
    """Return the loader for a given extension. Raises KeyError if unknown."""
    return LOADERS[extension.lower()]


def supported_extensions() -> list[str]:
    return list(LOADERS.keys())
