# rag.py
import os
import requests
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
import chromadb
from sentence_transformers import SentenceTransformer
import hashlib
import io
import torch # <-- Import torch to check for GPU

# --- Configuration ---
SOURCE_URLS = [
    "https://sdiopr.s3.ap-south-1.amazonaws.com/2023/June/16-Jun-23-2/2023_IJECC_101437/Revised-ms_IJECC_101437_v1.pdf",
    "https://en.wikipedia.org/wiki/Barahnaja",
    "https://en.wikipedia.org/wiki/Jhum",
    "https://icar.org.in/sites/default/files/2022-06/IITKA_Book_Traditional-Knowledge-in-Agriculture-English_0_0.pdf",
    "https://www.nabard.org/hindi/auth/writereaddata/tender/1507224157Paper-5-Agricultural-Tech-in-India-Dr.Joshi-%26-Varshney.pdf",
    "https://api.pageplace.de/preview/DT0400.9789389547627_A41783548/preview-9789389547627_A41783548.pdf",
    "https://en.wikipedia.org/wiki/Zero_Budget_Natural_Farming",
    "https://timesofindia.indiatimes.com/city/nagpur/bhandara-farmers-adopt-natural-farming-for-sustainable-yields/articleshow/122768671.cms",
    "https://en.wikipedia.org/wiki/Contour_plowing",
    "https://www.ijnrd.org/papers/IJNRD2208088.pdf",
    "https://apnews.com/article/fbf86b092b42303f5ae9d8af35aac8d9",
    "https://www.frontiersin.org/journals/political-science/articles/10.3389/fpos.2022.969835/full",
    "https://nishat2013.files.wordpress.com/2013/11/agronomy-book.pdf",
    "https://icar-crida.res.in/assets/img/Books/2003-04/ImpAgro.pdf",
    "https://raubikaner.org/wp-content/themes/theme2/PDF/AGRON-111.pdf",
    "https://k8449r.weebly.com/uploads/3/0/7/3/30731055/principles-of-agronomy-agricultural-meteorology-signed.pdf",
    "https://www.iari.res.in/files/Publication/important-publications/ClimateChange.pdf"
]
DB_DIRECTORY = "agri_db"
COLLECTION_NAME = "agriculture_docs"

def fetch_and_extract_text(url):
    """
    Fetches and extracts text from a PDF or Wikipedia URL.
    This combines your two previous functions into one.
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        if "wikipedia.org" in url:
            soup = BeautifulSoup(response.content, 'html.parser')
            content_div = soup.find(id="mw-content-text")
            return "\n".join(p.get_text() for p in content_div.find_all('p')) if content_div else None
        elif url.lower().endswith(".pdf"):
            with fitz.open(stream=io.BytesIO(response.content), filetype="pdf") as doc:
                return "".join(page.get_text() for page in doc)
    except Exception as e:
        print(f"Error processing {url}: {e}")
    return None

def chunk_text(text, chunk_size=1000, chunk_overlap=200):
    """Splits text into overlapping chunks."""
    if not text: return []
    words = text.split()
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size - chunk_overlap)]

def process_and_embed_sources():
    """Main function to process URLs, create embeddings, and store in ChromaDB."""
    print("Starting data ingestion...")
    
    # Check for an NVIDIA GPU and set the device for the model.
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device} for embedding...")
    
    # Load the embedding model onto the selected device (GPU or CPU).
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
    
    client = chromadb.PersistentClient(path=DB_DIRECTORY)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    for url in SOURCE_URLS:
        print(f"\n--- Processing: {url} ---")
        text = fetch_and_extract_text(url)
        if not text: continue

        chunks = chunk_text(text)
        if not chunks: continue
        
        # Create unique IDs for each chunk to prevent duplicates.
        ids = [f"{url}_{hashlib.md5(chunk.encode()).hexdigest()}" for chunk in chunks]
        
        # This step will be much faster on a GPU.
        embeddings = embedding_model.encode(chunks, show_progress_bar=True)
        
        collection.add(
            embeddings=embeddings.tolist(),
            documents=chunks,
            metadatas=[{"source": url} for _ in chunks],
            ids=ids
        )
        print(f"Successfully added {len(chunks)} chunks to the database.")

    print(f"\n--- Ingestion Complete. Total documents: {collection.count()} ---")

if __name__ == "__main__":
    process_and_embed_sources()
