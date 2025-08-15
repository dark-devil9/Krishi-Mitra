# translator.py
# Description: This module provides functions for language detection, transliteration, and translation.

from langdetect import detect, LangDetectException
from deep_translator import GoogleTranslator
# CHANGE: Import the transliteration library
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

def detect_language(text: str):
    """
    Detects the language of a given text.
    """
    try:
        return detect(text)
    except LangDetectException:
        print("Language detection failed. Defaulting to English.")
        return 'en'

# CHANGE: Added a new function for transliteration
def transliterate_to_latin(text: str, lang_code: str):
    """
    Transliterates text from an Indic script to the Latin script (English alphabet).
    e.g., "जयपुर" (hi) -> "jayapura"
    """
    if lang_code == 'hi': # Add other language codes like 'mr' for Marathi etc. if needed
        try:
            # Transliterate from Devanagari (used for Hindi) to IAST (a standard Latin script)
            return transliterate(text, sanscript.DEVANAGARI, sanscript.IAST)
        except Exception as e:
            print(f"Transliteration failed: {e}")
            return text # Fallback to original text
    return text


def translate_text(text: str, target_lang: str):
    """
    Translates text to a target language using deep-translator.
    """
    if not text or not text.strip():
        return ""
        
    try:
        translated_text = GoogleTranslator(source='auto', target=target_lang).translate(text)
        return translated_text
    except Exception as e:
        print(f"An error occurred during translation: {e}")
        return text

# Example for testing the new function
if __name__ == "__main__":
    hinglish_query = "jaipur mein mausam kaisa hai"
    hindi_query = "जयपुर में मौसम कैसा है?"

    # Test Hinglish (already in Latin script)
    lang_hinglish = detect_language(hinglish_query)
    transliterated_hinglish = transliterate_to_latin(hinglish_query, lang_hinglish)
    print(f"Hinglish Query: '{hinglish_query}' -> Transliterated: '{transliterated_hinglish}'")

    # Test Hindi (in Devanagari script)
    lang_hindi = detect_language(hindi_query)
    transliterated_hindi = transliterate_to_latin(hindi_query, lang_hindi)
    print(f"Hindi Query: '{hindi_query}' -> Transliterated: '{transliterated_hindi}'")
