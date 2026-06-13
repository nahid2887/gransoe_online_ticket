import requests
import urllib.parse
import hashlib
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

def translate_to_danish(text):
    """
    Translates a given English string to Danish using Google Translate's free API.
    Uses MD5 of the text for the cache key to avoid cache key length or character limitations.
    Caches the results to prevent repeated API calls.
    """
    if not text or not isinstance(text, str):
        return text

    stripped = text.strip()
    if not stripped:
        return text

    # Build md5 based cache key
    text_md5 = hashlib.md5(stripped.encode('utf-8')).hexdigest()
    cache_key = f"trans_en_da_{text_md5}"

    # Try retrieving from cache first
    cached_translation = cache.get(cache_key)
    if cached_translation is not None:
        return cached_translation

    try:
        url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=da&dt=t&q=' + urllib.parse.quote(stripped)
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            res_json = response.json()
            translated_chunks = []
            if res_json and isinstance(res_json, list) and len(res_json) > 0 and isinstance(res_json[0], list):
                for chunk in res_json[0]:
                    if chunk and isinstance(chunk, list) and len(chunk) > 0 and chunk[0]:
                        translated_chunks.append(chunk[0])
            translated_text = "".join(translated_chunks)
            if translated_text:
                # Cache the translation for 30 days (2592000 seconds)
                cache.set(cache_key, translated_text, 2592000)
                return translated_text
    except Exception as e:
        logger.warning(f"Failed to translate text to Danish: {e}")

    # Fallback to the original text on any failure
    return text
