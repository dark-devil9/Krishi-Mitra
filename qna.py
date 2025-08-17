# QNA.py
# Description: This module contains the core logic for answering questions
# by querying a ChromaDB database and using the Mistral AI API.

import os
from dotenv import load_dotenv
import chromadb
from sentence_transformers import SentenceTransformer
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

# --- Initialization ---
load_dotenv()

DB_DIRECTORY = "agri_db"
COLLECTION_NAME = "agriculture_docs"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY is not set. Please check your .env file.")

print("Initializing Q&A components...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
db_client = chromadb.PersistentClient(path=DB_DIRECTORY)
collection = db_client.get_collection(name=COLLECTION_NAME)
mistral_client = MistralClient(api_key=MISTRAL_API_KEY)
print("Q&A components initialized successfully.")


# --- Core RAG Logic ---

def get_answer_from_books(query: str, n_results: int = 7):
    """
    Takes a user query, retrieves context from ChromaDB, and generates a detailed answer.
    """
    print(f"Retrieving context for query: '{query}'")
    
    query_embedding = embedding_model.encode([query])[0].tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )
    context = results['documents'][0]
    
    # CHANGE: Updated prompt to ask for a concise answer.
    prompt = f"""
    You are an expert agricultural assistant. Based on the following context, please provide a concise and summarized answer to the user's question (around 3-4 sentences). If the context does not contain the answer, state that the information is not available in the provided documents. Do not use any markdown formatting like asterisks.

    CONTEXT:
    ---
    {"\n---\n".join(context)}
    ---

    QUESTION:
    {query}

    CONCISE ANSWER:
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
    """
    print("Sending comprehensive advisory prompt to Mistral AI...")
    
    # CHANGE: Added instruction for a concise summary at the end of the prompt.
    concise_prompt = full_prompt + "\n\nProvide a concise summary of your recommendation in a few key points."

    messages = [
        ChatMessage(role="user", content=concise_prompt)
    ]
    
    try:
        chat_response = mistral_client.chat(
            model="mistral-large-latest",
            messages=messages
        )
        answer = chat_response.choices[0].message.content
        return answer
    except Exception as e:
        print(f"Error during Mistral API call for advisory: {e}")
        return "I'm sorry, I encountered an error while trying to generate a detailed advisory. Please try again."

