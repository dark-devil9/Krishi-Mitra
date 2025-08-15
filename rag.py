# embed_sources.py
# Description: This script processes a list of URLs (both PDF and Wikipedia),
# extracts text, splits it into manageable chunks, generates embeddings,
# and stores them in a persistent ChromaDB database.

import os
import requests
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
import chromadb
from sentence_transformers import SentenceTransformer
import hashlib
import io

# --- Configuration ---
# ADD YOUR PDF AND WIKIPEDIA URLS HERE
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


DB_DIRECTORY = "agri_db"   # Directory to store the ChromaDB database
COLLECTION_NAME = "agriculture_docs" # Name of the collection in ChromaDB

# --- 1. Data Fetching and Text Extraction ---

def fetch_and_extract_pdf_url(url):
    """Downloads a PDF from a URL and extracts its text."""
    try:
        print(f"Fetching PDF from: {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Raise an exception for bad status codes

        # Open PDF from in-memory bytes
        pdf_file = io.BytesIO(response.content)
        doc = fitz.open(stream=pdf_file, filetype="pdf")
        
        text = ""
        for page in doc:
            text += page.get_text()
        print(f"Successfully extracted {len(text)} characters.")
        return text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching PDF URL {url}: {e}")
    except Exception as e:
        print(f"Error processing PDF from {url}: {e}")
    return None

def fetch_and_extract_wikipedia_url(url):
    """Fetches and extracts text content from a Wikipedia URL."""
    try:
        print(f"Fetching Wikipedia article from: {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the main content area of the article
        content_div = soup.find(id="mw-content-text")
        if not content_div:
            print("Could not find main content div.")
            return None
            
        # Extract text from paragraph tags, ignoring tables and other elements
        paragraphs = content_div.find_all('p')
        text = "\n".join([p.get_text() for p in paragraphs])
        
        print(f"Successfully extracted {len(text)} characters.")
        return text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Wikipedia URL {url}: {e}")
    except Exception as e:
        print(f"Error parsing Wikipedia page {url}: {e}")
    return None

def chunk_text(text, chunk_size=1000, chunk_overlap=200):
    """Splits text into overlapping chunks."""
    if not text:
        return []
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - chunk_overlap):
        chunks.append(" ".join(words[i:i + chunk_size]))
    return chunks

# --- 2. Main Processing Logic ---
def process_and_embed_sources():
    """
    Main function to process all URLs, create embeddings,
    and store them in ChromaDB.
    """
    print("Starting the source processing and embedding script...")

    # Initialize the embedding model
    print("Loading embedding model...")
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Embedding model loaded.")

    # Initialize ChromaDB client with persistence
    client = chromadb.PersistentClient(path=DB_DIRECTORY)

    # Get or create the collection
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"} # Using cosine similarity
    )

    # Process each URL
    total_urls = len(SOURCE_URLS)
    print(f"Found {total_urls} URLs to process.")

    for i, url in enumerate(SOURCE_URLS):
        print(f"\n--- Processing URL {i+1}/{total_urls}: {url} ---")
        text = None
        
        # Determine the type of URL and process accordingly
        if "wikipedia.org" in url:
            text = fetch_and_extract_wikipedia_url(url)
        elif url.lower().endswith(".pdf"):
            text = fetch_and_extract_pdf_url(url)
        else:
            print(f"Skipping unsupported URL type: {url}")
            continue

        if not text:
            print("Failed to extract text. Moving to next URL.")
            continue

        # Chunk text
        print("Chunking text...")
        chunks = chunk_text(text)
        if not chunks:
            print("No text chunks generated for this source.")
            continue
        
        print(f"Generated {len(chunks)} chunks.")

        # Generate unique IDs for each chunk
        ids = [f"{url}_{hashlib.md5(chunk.encode()).hexdigest()}" for chunk in chunks]

        # Generate embeddings
        print("Generating embeddings for chunks...")
        embeddings = embedding_model.encode(chunks, show_progress_bar=True)

        # Add to ChromaDB collection
        print("Adding chunks to the database...")
        try:
            collection.add(
                embeddings=embeddings.tolist(),
                documents=chunks,
                metadatas=[{"source": url} for _ in chunks],
                ids=ids
            )
            print(f"Successfully added {len(chunks)} chunks for {url}.")
        except Exception as e:
            print(f"Error adding chunks to database for {url}: {e}")

    print("\n-----------------------------------------")
    print("All sources have been processed and embedded.")
    print(f"Total documents in collection: {collection.count()}")
    print("-----------------------------------------")

if __name__ == "__main__":
    process_and_embed_sources()
