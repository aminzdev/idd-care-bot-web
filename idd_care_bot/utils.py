import re
import pandas as pd
from pathlib import Path


def clean_text(text: str) -> str:
    """Basic cleanup: collapse spaces, strip weird chars."""
    text = re.sub(r"\s+", " ", text)  # collapse whitespace
    return text.strip()


def chunk_text(text: str, max_len: int = 1200, overlap: int = 100) -> list[str]:
    """
    Split text into chunks of ~max_len characters with optional overlap.
    Works at sentence boundaries if possible.
    """
    text = clean_text(text)
    if len(text) <= max_len:
        return [text]

    # Naive sentence split
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current = [], ""

    for sent in sentences:
        if len(current) + len(sent) + 1 <= max_len:
            current += " " + sent
        else:
            chunks.append(current.strip())
            # start new chunk with overlap from previous
            current = current[-overlap:] + " " + sent

    if current.strip():
        chunks.append(current.strip())
    return chunks


def load_csvs(data_dir: str = "data"):
    """Load all CSVs in a folder into normalized dicts with chunked abstracts."""
    records = []
    for f in Path(data_dir).glob("*.csv"):
        df = pd.read_csv(f)
        for _, row in df.iterrows():
            title = clean_text(row["Title"])
            authors = clean_text(row["Authors"])
            abstract = clean_text(row["Abstract"])
            chunks = chunk_text(abstract)
            for chunk in chunks:
                records.append(
                    {
                        "title": title,
                        "authors": authors,
                        "abstract": chunk,
                        "source": f.name,
                    }
                )
    return records
