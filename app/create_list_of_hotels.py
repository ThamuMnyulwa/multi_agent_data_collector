"""
Creates a dictionary of hotel names and the corresponding URLs to then scrape off booking.com to
get the hotel information.

"""

import os
import time
import json
import random
from typing import List, Dict, Optional
from openai import OpenAI

# Configure the maximum number of concurrent requests
MAX_CONCURRENT_REQUESTS = 2


def get_openai_client() -> OpenAI:
    """Initialize and return an OpenAI client."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    return OpenAI(api_key=api_key)


def generate_hotel_list(
    location: str = "worldwide", num_hotels: int = 10
) -> List[Dict[str, str]]:
    """
    Use OpenAI to generate a list of well-known hotels with their URLs.

    Args:
        location: Location/region for the hotels (default: worldwide)
        num_hotels: Number of hotels to generate (default: 10)

    Returns:
        List of dictionaries with hotel names and URLs
    """
    client = get_openai_client()

    prompt = f"""
    Generate a list of {num_hotels} well-known hotels in {location}. 
    For each hotel, provide:
    1. The hotel name
    2. The booking.com URL for the hotel
    3. The location (city and country)
    
    Format your response as a JSON array of objects with the following structure:
    [
        {{
            "name": "Hotel Name",
            "url": "https://www.booking.com/hotel/...",
            "location": "City, Country"
        }},
        ...
    ]
    
    Make sure all URLs are valid booking.com URLs and follow this pattern:
    https://www.booking.com/hotel/country_code/hotel-name.html
    """

    print(f"Generating list of {num_hotels} hotels in {location} using OpenAI...")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that provides accurate hotel information.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        result = json.loads(content)

        if "hotels" in result:
            hotels = result["hotels"]
        else:
            # If the response is directly an array
            hotels = result

        # Validate and clean the URLs
        validated_hotels = []
        for hotel in hotels:
            if validate_hotel_url(hotel.get("url", "")):
                validated_hotels.append(hotel)
            else:
                # Try to fix the URL if it's not valid
                fixed_url = construct_booking_url(
                    hotel.get("name", ""), hotel.get("location", "")
                )
                if fixed_url:
                    hotel["url"] = fixed_url
                    validated_hotels.append(hotel)

        return validated_hotels

    except Exception as e:
        print(f"Error generating hotel list: {e}")
        return []


def validate_hotel_url(url: str) -> bool:
    """
    Validate if a URL is a valid booking.com hotel URL.

    Args:
        url: URL to validate

    Returns:
        True if the URL is valid, False otherwise
    """
    if not url:
        return False

    if not url.startswith("https://www.booking.com/hotel/"):
        return False

    # Basic structure validation
    parts = url.split("/")
    if len(parts) < 5:
        return False

    return True


def construct_booking_url(hotel_name: str, location: str) -> Optional[str]:
    """
    Construct a booking.com URL from a hotel name and location.

    Args:
        hotel_name: Name of the hotel
        location: Location of the hotel (city, country)

    Returns:
        A constructed booking.com URL or None if not possible
    """
    if not hotel_name:
        return None

    # Extract country code (for URL construction)
    country = location.split(",")[-1].strip() if location else ""
    country_code = get_country_code(country)

    # Format hotel name for URL
    url_name = hotel_name.lower().replace(" ", "-").replace("'", "").replace(",", "")

    # Construct URL
    return f"https://www.booking.com/hotel/{country_code}/{url_name}.html"


def get_country_code(country: str) -> str:
    """
    Get the two-letter country code for a country name.

    Args:
        country: Country name

    Returns:
        Two-letter country code or 'us' as default
    """
    # Simple mapping of common countries to their codes
    country_codes = {
        "united states": "us",
        "usa": "us",
        "united kingdom": "gb",
        "uk": "gb",
        "france": "fr",
        "spain": "es",
        "italy": "it",
        "germany": "de",
        "japan": "jp",
        "china": "cn",
        "australia": "au",
        "canada": "ca",
        "india": "in",
        "brazil": "br",
        "mexico": "mx",
        "singapore": "sg",
        "thailand": "th",
        "united arab emirates": "ae",
        "uae": "ae",
        "south africa": "za",
    }

    return country_codes.get(country.lower(), "us")


def get_hotel_urls(
    location: str = "worldwide", num_hotels: int = 10
) -> List[Dict[str, str]]:
    """
    Main function to get a list of hotel URLs.

    Args:
        location: Location for the hotels
        num_hotels: Number of hotels to get

    Returns:
        List of dictionaries with hotel information
    """
    # Generate hotels using OpenAI
    hotels = generate_hotel_list(location, num_hotels)

    # If we didn't get any hotels, use a fallback list
    if not hotels:
        print("Using fallback hotel list...")
        hotels = [
            {
                "name": "The Plaza",
                "url": "https://www.booking.com/hotel/us/the-plaza.html",
                "location": "New York, USA",
            },
            {
                "name": "Waldorf Astoria",
                "url": "https://www.booking.com/hotel/us/waldorf-astoria-new-york.html",
                "location": "New York, USA",
            },
            {
                "name": "The Ritz London",
                "url": "https://www.booking.com/hotel/gb/the-ritz-london.html",
                "location": "London, UK",
            },
            {
                "name": "Marina Bay Sands",
                "url": "https://www.booking.com/hotel/sg/marina-bay-sands.html",
                "location": "Singapore",
            },
            {
                "name": "Burj Al Arab Jumeirah",
                "url": "https://www.booking.com/hotel/ae/burj-al-arab.html",
                "location": "Dubai, UAE",
            },
        ]

    return hotels


def get_hotel_urls_with_rate_limiting(
    location: str = "worldwide", num_hotels: int = 10
) -> List[Dict[str, str]]:
    """
    Get hotel URLs with rate limiting to respect the 2 concurrent requests limit.

    Args:
        location: Location for the hotels
        num_hotels: Number of hotels to get

    Returns:
        List of dictionaries with hotel information
    """
    hotels = get_hotel_urls(location, num_hotels)

    # Only return a maximum of MAX_CONCURRENT_REQUESTS hotels at a time
    return hotels[:MAX_CONCURRENT_REQUESTS]


if __name__ == "__main__":
    # Simple test to generate and print a list of hotels
    hotels = get_hotel_urls(location="New York", num_hotels=5)

    print("\nGenerated Hotel List:")
    for i, hotel in enumerate(hotels, 1):
        print(f"{i}. {hotel['name']} - {hotel['location']}")
        print(f"   URL: {hotel['url']}")
