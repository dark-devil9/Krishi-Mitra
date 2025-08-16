# ask_question.py
# Description: This script allows a user to ask a question, retrieves
# relevant text chunks from the ChromaDB database, and uses the Mistral AI API
# to generate an answer based on the retrieved context.

import os
from dotenv import load_dotenv

import chromadb
from sentence_transformers import SentenceTransformer
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

load_dotenv()

# --- Configuration ---
DB_DIRECTORY = "agri_db"
COLLECTION_NAME = "agriculture_docs"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY") # Recommended: Set as environment variable
# If not using an environment variable, uncomment and paste your key here:
# MISTRAL_API_KEY = "YOUR_MISTRAL_API_KEY"

# --- 1. Initialization ---
def initialize_components(device="cpu"):
    """Initializes and returns all necessary components."""
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY is not set. Please set it as an environment variable or in the script.")

    print(f"Loading embedding model on device: {device}")
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2', device=device)

    print("Connecting to ChromaDB...")
    client = chromadb.PersistentClient(path=DB_DIRECTORY)
    # FIX: Use get_or_create_collection to prevent crashes if the collection doesn't exist yet.
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    print("Initializing Mistral client...")
    mistral_client = MistralClient(api_key=MISTRAL_API_KEY)

    print("Initialization complete. Ready to ask questions.")
    return embedding_model, collection, mistral_client

# --- 2. Core RAG Logic ---
def retrieve_context(query, collection, embedding_model, n_results=5):
    """Retrieves relevant context from the database based on the query."""
    query_embedding = embedding_model.encode([query])[0].tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )

    return results['documents'][0]

def generate_answer(query, context, mistral_client):
    """Generates an answer using Mistral AI based on the query and context."""

    # FIX: Join the context into a string *before* the f-string to avoid a SyntaxError.
    context_str = "\n---\n".join(context)

    # Now, use the pre-formatted context_str in the prompt.
    prompt = f"""
    You are an expert agricultural assistant. Based on the following context extracted from reference books, please provide a clear and concise answer to the user's question. If the context does not contain the answer, state that the information is not available in the provided documents.

    CONTEXT:
    ---
    {context_str}
    ---

    QUESTION:
    {query}

    ANSWER:
    """

    messages = [
        ChatMessage(role="user", content=prompt)
    ]

    print("\nSending request to Mistral AI...")
    chat_response = mistral_client.chat(
        model="mistral-large-latest", # Or another suitable model like 'mistral-small'
        messages=messages
    )

    return chat_response.choices[0].message.content

# --- 3. Main Interaction Loop ---
def main():
    """Main function to run the interactive question-answering loop."""
    try:
        embedding_model, collection, mistral_client = initialize_components()
    except Exception as e:
        print(f"Error during initialization: {e}")
        return

    print("\n--- Agricultural RAG Model ---")
    print("Ask a question about your documents. Type 'exit' to quit.")

    while True:
        user_query = input("\nYour Question: ")
        if user_query.lower() == 'exit':
            print("Exiting. Goodbye!")
            break

        # 1. Retrieve context
        print("Retrieving relevant information from your books...")
        retrieved_context = retrieve_context(user_query, collection, embedding_model)

        # 2. Generate answer
        answer = generate_answer(user_query, retrieved_context, mistral_client)

        # 3. Display result
        print("\n--- Answer ---")
        print(answer)
        print("\n--- Sources ---")
        # Note: This shows the raw text chunks. For a production system,
        # you might link back to the source PDF and page number.
        for i, doc in enumerate(retrieved_context):
             print(f"[{i+1}] {doc[:100]}...") # Print first 100 chars of each source chunk
        print("\n-----------------")

if __name__ == "__main__":
    main()
