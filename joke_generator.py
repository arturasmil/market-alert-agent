#!/usr/bin/env python3
"""
Random Joke Generator - Fetches jokes from external APIs
Supports multiple joke sources and categories
"""

import requests
import random
from typing import Dict, Any, List, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JokeGenerator:
    """Generates random jokes from multiple external APIs"""
    
    # JokeAPI endpoint - supports multiple formats and categories
    JOKE_API_URL = "https://v2.jokeapi.dev/joke"
    
    # Official Joke API - simple format
    OFFICIAL_JOKE_API_URL = "https://official-joke-api.appspot.com/jokes/random"
    
    # QuotesAPI alternative endpoint
    USELESS_FACTS_API_URL = "https://uselessfacts.jsondatabase.com/random"
    
    # Supported joke categories from JokeAPI
    JOKE_CATEGORIES = ["general", "knock-knock", "programming", "spooky"]
    
    # Rate limiting headers
    HEADERS = {
        "User-Agent": "Joke-Generator/1.0 (Contact: email@example.com)",
    }
    
    @classmethod
    def get_random_joke(cls, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch a random joke from JokeAPI
        
        Args:
            category: Optional joke category (general, knock-knock, programming, spooky)
                     If None, selects random category
            
        Returns:
            Dictionary containing joke data with keys: setup, delivery, category, type
        """
        if category is None:
            category = random.choice(cls.JOKE_CATEGORIES)
        
        logger.info(f"Fetching joke from category: {category}")
        
        try:
            url = f"{cls.JOKE_API_URL}/{category}"
            params = {
                "format": "json",
                "type": "single,twopart"  # Accept both single and two-part jokes
            }
            
            response = requests.get(
                url,
                params=params,
                headers=cls.HEADERS,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("error"):
                logger.warning(f"API returned error: {data.get('message')}")
                return cls._format_error_joke()
            
            joke_type = data.get("type", "single")
            
            if joke_type == "single":
                return {
                    "setup": data.get("joke", ""),
                    "delivery": None,
                    "category": data.get("category", "general"),
                    "type": "single",
                    "source": "JokeAPI"
                }
            else:  # two-part joke
                return {
                    "setup": data.get("setup", ""),
                    "delivery": data.get("delivery", ""),
                    "category": data.get("category", "general"),
                    "type": "twopart",
                    "source": "JokeAPI"
                }
        
        except requests.RequestException as e:
            logger.error(f"Error fetching joke from JokeAPI: {e}")
            # Fallback to official joke API
            return cls.get_official_joke()

    @classmethod
    def get_official_joke(cls) -> Dict[str, Any]:
        """
        Fetch a joke from Official Joke API (fallback)
        
        Returns:
            Dictionary containing joke data
        """
        logger.info("Fetching joke from Official Joke API")
        
        try:
            response = requests.get(
                cls.OFFICIAL_JOKE_API_URL,
                headers=cls.HEADERS,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            return {
                "setup": data.get("setup", ""),
                "delivery": data.get("punchline", ""),
                "category": data.get("type", "general"),
                "type": "twopart",
                "source": "Official Joke API"
            }
        
        except requests.RequestException as e:
            logger.error(f"Error fetching from Official Joke API: {e}")
            return cls._get_local_joke()

    @classmethod
    def _get_local_joke(cls) -> Dict[str, Any]:
        """
        Return a local fallback joke when APIs are unavailable
        
        Returns:
            Dictionary containing joke data
        """
        local_jokes = [
            {
                "setup": "Why don't scientists trust atoms?",
                "delivery": "Because they make up everything!",
                "category": "general",
                "type": "twopart",
                "source": "Local Fallback"
            },
            {
                "setup": "Why did the scarecrow win an award?",
                "delivery": "He was outstanding in his field!",
                "category": "general",
                "type": "twopart",
                "source": "Local Fallback"
            },
            {
                "setup": "What do you call a fake noodle?",
                "delivery": "An impasta!",
                "category": "general",
                "type": "twopart",
                "source": "Local Fallback"
            },
            {
                "setup": "Why don't eggs tell jokes?",
                "delivery": "They'd crack each other up!",
                "category": "general",
                "type": "twopart",
                "source": "Local Fallback"
            },
            {
                "setup": "What's the object-oriented way to become wealthy?",
                "delivery": "Inheritance!",
                "category": "programming",
                "type": "twopart",
                "source": "Local Fallback"
            },
        ]
        
        selected_joke = random.choice(local_jokes)
        logger.info(f"Using local fallback joke from {selected_joke['source']}")
        return selected_joke

    @classmethod
    def _format_error_joke(cls) -> Dict[str, Any]:
        """Return a meta-joke about API errors"""
        return {
            "setup": "Why did the API go to therapy?",
            "delivery": "It had too many issues to handle!",
            "category": "programming",
            "type": "twopart",
            "source": "Meta Joke"
        }

    @classmethod
    def get_multiple_jokes(cls, count: int = 5) -> List[Dict[str, Any]]:
        """
        Fetch multiple random jokes
        
        Args:
            count: Number of jokes to fetch
            
        Returns:
            List of joke dictionaries
        """
        jokes = []
        logger.info(f"Fetching {count} jokes")
        
        for i in range(count):
            joke = cls.get_random_joke()
            jokes.append(joke)
            logger.debug(f"Fetched joke {i + 1}/{count}")
        
        return jokes

    @classmethod
    def get_joke_by_category(cls, category: str) -> Dict[str, Any]:
        """
        Get a joke from a specific category
        
        Args:
            category: Joke category (general, knock-knock, programming, spooky)
            
        Returns:
            Dictionary containing joke data
        """
        if category not in cls.JOKE_CATEGORIES:
            logger.warning(f"Unknown category: {category}. Using random category.")
            category = random.choice(cls.JOKE_CATEGORIES)
        
        return cls.get_random_joke(category=category)


def format_joke_output(joke: Dict[str, Any]) -> str:
    """
    Format joke for display
    
    Args:
        joke: Dictionary containing joke data
        
    Returns:
        Formatted joke string
    """
    category = joke.get("category", "N/A").upper()
    source = joke.get("source", "Unknown")
    
    output = f"📝 {category} JOKE ({source})\n"
    output += f"{'─' * 40}\n"
    
    setup = joke.get("setup", "")
    delivery = joke.get("delivery")
    
    output += f"Q: {setup}\n"
    
    if delivery:
        output += f"A: {delivery}\n"
    
    output += f"{'─' * 40}\n"
    
    return output


def main():
    """Main execution"""
    logger.info("Starting Random Joke Generator")
    
    # Example 1: Get a single random joke
    print("\n🎭 SINGLE RANDOM JOKE\n")
    joke = JokeGenerator.get_random_joke()
    print(format_joke_output(joke))
    
    # Example 2: Get a joke from a specific category
    print("🎭 PROGRAMMING JOKE\n")
    programming_joke = JokeGenerator.get_joke_by_category("programming")
    print(format_joke_output(programming_joke))
    
    # Example 3: Get multiple jokes
    print("🎭 5 RANDOM JOKES\n")
    multiple_jokes = JokeGenerator.get_multiple_jokes(count=5)
    for i, joke in enumerate(multiple_jokes, 1):
        print(f"[Joke {i}]")
        print(format_joke_output(joke))
    
    # Example 4: Get a knock-knock joke
    print("🎭 KNOCK-KNOCK JOKE\n")
    knock_knock = JokeGenerator.get_joke_by_category("knock-knock")
    print(format_joke_output(knock_knock))
    
    logger.info("Random Joke Generator completed")


if __name__ == "__main__":
    main()
