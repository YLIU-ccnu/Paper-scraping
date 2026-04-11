import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_strategy() -> dict:
    strategy_file = Path(__file__).resolve().parent / "config" / "default_strategy.json"
    with open(strategy_file, "r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=1)
def load_inspire_profiles() -> dict:
    profiles_file = Path(__file__).resolve().parent / "config" / "inspire_profiles.json"
    with open(profiles_file, "r", encoding="utf-8") as file:
        return json.load(file)


STRATEGY = load_strategy()
INSPIRE_PROFILES = load_inspire_profiles()

ARXIV_API = STRATEGY["arxiv_api"]
INSPIRE_API = STRATEGY["inspire_api"]
HEADERS = STRATEGY["headers"]
NS = STRATEGY["namespaces"]
SCIENCE_CATEGORIES = set(STRATEGY["science_categories"])
ML_CATEGORIES = set(STRATEGY["ml_categories"])
ML_KEYWORDS = STRATEGY["ml_keywords"]
SCIENCE_KEYWORDS = STRATEGY["science_keywords"]
ARXIV_QUERY_ML_TERMS = STRATEGY["arxiv_query_ml_terms"]
INSPIRE_DEFAULT_QUERY = STRATEGY["inspire_default_query"]
INSPIRE_DEFAULT_TOPCITE = STRATEGY["inspire_default_topcite"]
AI_FILTER_SYSTEM_PROMPT = STRATEGY["ai_filter_system_prompt"]
AI_FILTER_USER_PROMPT_TEMPLATE = STRATEGY["ai_filter_user_prompt_template"]
THEME_ORDER = STRATEGY["theme_order"]
THEME_TITLES = STRATEGY["theme_titles"]
