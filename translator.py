# translator.py
# Description: This module provides functions for language detection, transliteration, and translation.

from langdetect import detect, LangDetectException
from deep_translator import GoogleTranslator
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

def is_latin_script(text: str):
    """Checks if the text contains only Latin (English) alphabet characters."""
    try:
        text.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False

def detect_language(text: str):
    """
    Detects the language of a given text.
    """
    try:
        return detect(text)
    except LangDetectException:
        print("Language detection failed. Defaulting to English.")
        return 'en'

def transliterate_to_latin(text: str, lang_code: str):
    """
    Transliterates text from an Indic script to the Latin script (English alphabet).
    """
    # List of languages that use Devanagari script
    devanagari_langs = ['hi', 'mr', 'ne', 'sa', 'kok']
    if lang_code in devanagari_langs:
        try:
            return transliterate(text, sanscript.DEVANAGARI, sanscript.IAST)
        except Exception as e:
            print(f"Transliteration failed: {e}")
            return text
    return text


def translate_text(text: str, target_lang: str, source_lang: str = 'auto'):
    """
    Translates text to a target language using deep-translator.
    """
    if not text or not text.strip():
        return ""
        
    try:
        # Added source_lang parameter for more control
        translated_text = GoogleTranslator(source=source_lang, target=target_lang).translate(text)
        return translated_text
    except Exception as e:
        print(f"An error occurred during translation: {e}")
        return text
