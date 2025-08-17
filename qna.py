# QNA.py
# CHANGE: Renamed from ask_question.py to reflect its role as a Q&A module.
# Description: This module contains the core logic for answering questions
# by querying a ChromaDB database and using the Mistral AI API.

import os
from dotenv import load_dotenv
import chromadb
from sentence_transformers import SentenceTransformer
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

# --- 1. Initialization (Moved to top level) ---
# CHANGE: This code now runs only ONCE when the module is first imported by main.py,
# which is much more efficient than initializing on every API call.

load_dotenv()

# --- Configuration ---
DB_DIRECTORY = "agri_db"
COLLECTION_NAME = "agriculture_docs"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY is not set. Please check your .env file.")

print("Initializing Q&A components...")

# Initialize all components and store them as global variables within this module
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
db_client = chromadb.PersistentClient(path=DB_DIRECTORY)
collection = db_client.get_collection(name=COLLECTION_NAME)
mistral_client = MistralClient(api_key=MISTRAL_API_KEY)

print("Q&A components initialized successfully.")

# --- 2. Core RAG Logic (Combined into a single function) ---
# CHANGE: Combined the logic into one main function that your FastAPI server can call.

def get_answer_from_books(query: str, n_results: int = 5):
    """
    Takes a user query, retrieves context from ChromaDB, and generates an answer using Mistral.
    
    Args:
        query (str): The user's question.
        n_results (int): The number of context chunks to retrieve.

    Returns:
        tuple[str, list[str]]: A tuple containing the generated answer and the list of source documents.
    """
    print(f"Retrieving context for query: '{query}'")
    
    # Step 1: Retrieve context from the database
    query_embedding = embedding_model.encode([query])[0].tolist()
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )
    
    context = results['documents'][0]
    
    # Step 2: Generate an answer using the context
    print("Generating answer with Mistral AI...")
    prompt = f"""
    You are an expert agricultural assistant. Based on the following context extracted from reference books, please provide a clear and concise answer to the user's question. If the context does not contain the answer, state that the information is not available in the provided documents.

    CONTEXT:
    ---
    {"\n---\n".join(context)}
    ---

    QUESTION:
    {query}

    ANSWER:
    """
    
    messages = [
        ChatMessage(role="user", content=prompt)
    ]
    
    chat_response = mistral_client.chat(
        model="mistral-large-latest",
        messages=messages
    )
    
    answer = chat_response.choices[0].message.content
    
    return answer, context

def generate_advisory_answer(full_prompt: str):
    """
    Sends a detailed, combined prompt to Mistral to get a synthesized advisory answer.
    This is used for complex queries that require multiple data sources.
    """
    print("Sending comprehensive advisory prompt to Mistral AI...")
    
    messages = [
        ChatMessage(role="user", content=full_prompt)
    ]
    
    try:
        chat_response = mistral_client.chat(
            model="mistral-large-latest", # Use a powerful model for reasoning
            messages=messages
        )
        answer = chat_response.choices[0].message.content
        # For advisory answers, we don't return separate sources, as the answer is a synthesis of all of them.
        return answer
    except Exception as e:
        print(f"Error during Mistral API call for advisory: {e}")
        return "I'm sorry, I encountered an error while trying to generate a detailed advisory. Please try again."


# --- 3. Main Interaction Loop (Kept for standalone testing) ---
# CHANGE: The interactive loop is now inside an `if __name__ == "__main__":` block.
# This means it will ONLY run if you execute this file directly (e.g., `python QNA.py`).
# It will NOT run when this file is imported by `main.py`.

if __name__ == "__main__":
    print("\n--- Running QNA.py in standalone test mode ---")
    print("Ask a question about your documents. Type 'exit' to quit.")

    while True:
        user_query = input("\nYour Question: ")
        if user_query.lower() == 'exit':
            print("Exiting. Goodbye!")
            break
        
        # Call the main logic function
        answer, retrieved_context = get_answer_from_books(user_query)
        
        # Display result
        print("\n--- Answer ---")
        print(answer)
        print("\n--- Sources ---")
        for i, doc in enumerate(retrieved_context):
            print(f"[{i+1}] {doc[:100]}...")
        print("\n-----------------")
