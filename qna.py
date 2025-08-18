# QNA.py
# Description: This module contains the core logic for answering questions
# by querying a ChromaDB database and using the Mistral AI API.

import os
from dotenv import load_dotenv
import chromadb
from sentence_transformers import SentenceTransformer
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
import json

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
    
    # Improved prompt for better responses
    prompt = f"""
    You are an expert agricultural assistant named Krishi Mitra. Based on the following context, please provide a helpful and informative answer to the user's question.

    IMPORTANT GUIDELINES:
    1. If the context contains relevant information, provide a clear, practical answer in 2-4 sentences
    2. If the context doesn't contain the answer, say exactly: "Not available in my documents."
    3. Be conversational and helpful - you're talking to farmers
    4. Don't use markdown formatting like asterisks
    5. If the question is about weather, crops, farming practices, or agricultural advice, try to be as helpful as possible
    6. If you can provide general agricultural knowledge even without specific context, do so briefly

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
    
    try:
        chat_response = mistral_client.chat(
            model="mistral-large-latest",
            messages=messages
        )
        
        answer = chat_response.choices[0].message.content
        return answer, context
    except Exception as e:
        print(f"Error during Mistral API call: {e}")
        return "I'm sorry, I encountered an error while processing your question. Please try again.", context


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


def run_llm_json(system_prompt: str, user_input: str):
    """
    Call LLM to produce strict JSON. Attempts to parse and return a dict.
    """
    messages = [
        ChatMessage(role="system", content=system_prompt + "\nReturn ONLY valid JSON, no explanations."),
        ChatMessage(role="user", content=user_input),
    ]
    try:
        chat_response = mistral_client.chat(model="mistral-large-latest", messages=messages)
        content = chat_response.choices[0].message.content.strip()
        # Strip code fences if present
        if content.startswith("```"):
            content = content.strip('`')
            if content.startswith("json"):
                content = content[4:]
        # Fallback: extract JSON substring
        try:
            return json.loads(content)
        except Exception:
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1 and end > start:
                return json.loads(content[start:end+1])
            return {}
    except Exception as e:
        print(f"LLM JSON call failed: {e}")
        return {}


def run_llm_text(system_prompt: str, user_input: str) -> str:
    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_input),
    ]
    try:
        chat_response = mistral_client.chat(model="mistral-large-latest", messages=messages)
        return chat_response.choices[0].message.content
    except Exception as e:
        print(f"LLM text call failed: {e}")
        return "I'm sorry, I encountered an error. Please try again."