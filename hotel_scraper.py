import os
import sys
import json
import logging
import time
import random
import re
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Dependencies: openai, firecrawl-py, pydantic, beautifulsoup4, requests
from openai import OpenAI

client = OpenAI()
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
from firecrawl import FirecrawlApp  # Ensure firecrawl-py is installed

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# --- Agent 1: URL Collector using OpenAI GPT-4 ---
def get_hotels_list(location: str, count: int = 10) -> Dict[str, str]:
    """
    Use OpenAI's GPT-4 to generate a dictionary mapping hotel names to Booking.com URLs
    for a given location.
    """
    logging.info(f"Requesting {count} hotel names and URLs for location: {location}")
    # Ensure OpenAI API key is set
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logging.error(
            "OpenAI API key not found. Set OPENAI_API_KEY environment variable."
        )
        raise RuntimeError("OpenAI API key is missing.")

    system_prompt = "You are a travel assistant that returns hotel data in JSON format."
    user_prompt = (
        f"List {count} well-known hotels in {location}.\n"
        "For each hotel, provide the hotel name and its Booking.com URL. \n"
        "Return a JSON object where each key is the hotel name and each value is the URL. \n"
        "Make sure all URLs follow the pattern: https://www.booking.com/hotel/<country_code>/<hotel-name>.html"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )
    except Exception as e:
        logging.error(f"OpenAI API request failed: {e}")
        raise RuntimeError(f"OpenAI API request failed: {e}")

    content = response.choices[0].message.content.strip()
    logging.debug(f"OpenAI raw output: {content}")
    try:
        hotels = json.loads(content)
        if not isinstance(hotels, dict):
            raise ValueError("JSON is not a dictionary.")
    except Exception as e:
        logging.error(f"Failed to parse OpenAI response as JSON: {e}")
        raise RuntimeError(f"Invalid JSON from OpenAI: {e}")
    if not hotels:
        logging.error("OpenAI returned an empty hotel list.")
        raise RuntimeError("No hotels found in OpenAI response.")
    logging.info(f"Retrieved {len(hotels)} hotels from OpenAI.")
    return hotels


# --- Agent 2: Web Scraper using Firecrawl ---
class HotelData(BaseModel):
    name: Optional[str] = Field(None, description="Name of the hotel")
    address: Optional[str] = Field(None, description="Address of the hotel")
    price: Optional[str] = Field(None, description="Price per night")
    description: Optional[str] = Field(
        None, description="Brief description of the hotel"
    )


def scrape_hotel_data(
    hotel_url: str, firecrawl_app: FirecrawlApp
) -> Dict[str, Optional[str]]:
    """
    Use Firecrawl to scrape hotel details from a Booking.com URL.
    Extract structured data based on our defined schema.
    """
    logging.info(f"Scraping hotel page: {hotel_url}")
    schema_json = HotelData.model_json_schema()
    extract_prompt = (
        "Extract the following details from the page: hotel name, address, price per night, "
        "and a brief description. Format the output as a JSON object with keys: name, address, price, description."
    )
    extract_config = {"schema": schema_json, "prompt": extract_prompt}
    try:
        # Removed the "render": True parameter (not supported)
        result = firecrawl_app.scrape_url(
            hotel_url,
            params={
                "formats": ["extract", "html"],
                "extract": extract_config,
            },
        )
    except Exception as e:
        logging.error(f"Firecrawl scraping failed for {hotel_url}: {e}")
        raise RuntimeError(f"Firecrawl scraping failed for {hotel_url}: {e}")

    data = result.get("extract")
    raw_html = result.get("html")
    if data is None:
        logging.error(f"No extraction data returned for {hotel_url}.")
        raise RuntimeError(f"Failed to extract data from {hotel_url}")
    if not isinstance(data, dict):
        logging.error(f"Unexpected extract format for {hotel_url}: {data}")
        raise RuntimeError(f"Unexpected extract format for {hotel_url}")
    return {"data": data, "html": raw_html}


# --- Agent 3: Validator & Cleaner ---
def validate_and_fix(
    hotel_name: str, hotel_data: Dict[str, Optional[str]], raw_html: str
) -> Dict[str, Optional[str]]:
    """
    Validate that hotel_data contains all required fields.
    If any field is missing or empty, attempt to fix it using HTML parsing.
    """
    logging.info(f"Validating data for hotel: {hotel_name}")
    soup = BeautifulSoup(raw_html or "", "html.parser") if raw_html else None

    # Validate 'name'
    name = hotel_data.get("name")
    if not name or not name.strip():
        logging.warning(f"Name missing for {hotel_name}; using initial hotel name.")
        name = hotel_name
    else:
        name = name.strip()

    # Validate 'address'
    address = hotel_data.get("address")
    if (not address or not address.strip()) and soup:
        logging.warning(
            f"Address missing for {hotel_name}; trying to extract from HTML."
        )
        addr_elem = soup.select_one(".hp_address_subtitle")
        if addr_elem:
            address = addr_elem.get_text(strip=True)
            logging.info(f"Address found in HTML for {hotel_name}: {address}")
    address = address.strip() if address else None

    # Validate 'price'
    price = hotel_data.get("price")
    if (not price or not price.strip()) and soup:
        logging.warning(f"Price missing for {hotel_name}; attempting to find in HTML.")
        text = soup.get_text(" ", strip=True)
        match = re.search(r"(\$|€|£|₹|¥)[\d,]+(?:\.\d{2})?", text)
        if match:
            price = match.group(0)
            logging.info(f"Price found in HTML for {hotel_name}: {price}")
    price = price.strip() if price else None

    # Validate 'description'
    description = hotel_data.get("description")
    if (not description or not description.strip()) and soup:
        logging.warning(
            f"Description missing for {hotel_name}; trying to extract from HTML."
        )
        desc_elem = soup.select_one("#property_description_content")
        if desc_elem:
            description = desc_elem.get_text(" ", strip=True)
            logging.info(f"Description found in HTML for {hotel_name}.")
    description = " ".join(description.split()).strip() if description else None

    return {
        "name": name,
        "address": address,
        "price": price,
        "description": description,
        "url": None,  # URL will be added later.
    }


# --- Firecrawl Client Wrapper ---
class FirecrawlClientWrapper:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FIRECRAWL_API_KEY")
        if not self.api_key:
            logging.error(
                "Firecrawl API key not found. Set FIRECRAWL_API_KEY environment variable."
            )
            raise RuntimeError("Missing Firecrawl API key.")
        self.app = FirecrawlApp(api_key=self.api_key)

    def scrape_url(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Scrape a URL using Firecrawl."""
        return self.app.scrape_url(url, params=params)


# --- Main Process ---
def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Hotel Data Collector")
    parser.add_argument(
        "--location", required=True, help="Location (e.g., 'Cape Town, South Africa')"
    )
    parser.add_argument(
        "--count", type=int, default=10, help="Number of hotels to retrieve"
    )
    parser.add_argument("--output", default="hotels.json", help="Output JSON file name")
    args = parser.parse_args()

    location = args.location
    num_hotels = args.count
    output_file = args.output

    # Agent 1: Generate hotel list using OpenAI GPT-4
    hotels_dict = get_hotels_list(location, num_hotels)
    if not hotels_dict:
        logging.error("No hotel list generated; exiting.")
        sys.exit(1)

    # Initialize Firecrawl client wrapper
    fc_client = FirecrawlClientWrapper()

    final_results = []
    for hotel_name, base_url in hotels_dict.items():
        # Append check-in/check-out dates to encourage price display
        checkin = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        checkout = (datetime.now() + timedelta(days=31)).strftime("%Y-%m-%d")
        if "?" in base_url:
            hotel_url = base_url
        else:
            hotel_url = f"{base_url}?checkin={checkin}&checkout={checkout}&group_adults=2&no_rooms=1&group_children=0"
        try:
            scrape_result = fc_client.scrape_url(
                hotel_url,
                params={
                    "formats": ["extract", "html"],
                    "extract": {
                        "schema": HotelData.model_json_schema(),
                        "prompt": (
                            "Extract hotel name, address, price per night, and a brief description from the page."
                        ),
                    },
                    # Removed "render": True (no longer supported)
                },
            )
        except Exception as e:
            logging.error(f"Error scraping {hotel_name} at {hotel_url}: {e}")
            continue

        data = scrape_result.get("extract")
        raw_html = scrape_result.get("html", "")
        if data is None:
            logging.error(f"No data extracted for {hotel_name}.")
            continue

        # Agent 3: Validate and attempt to fix the data
        cleaned_data = validate_and_fix(hotel_name, data, raw_html)
        cleaned_data["url"] = base_url  # Save the original URL
        final_results.append(cleaned_data)
        logging.info(f"Processed data for hotel: {hotel_name}")

    if not final_results:
        logging.error("No hotel data collected; exiting.")
        sys.exit(1)

    # Save final results as JSON
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_results, f, indent=2, ensure_ascii=False)
        logging.info(f"Saved {len(final_results)} hotel entries to {output_file}")
    except Exception as e:
        logging.error(f"Error saving JSON output: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
