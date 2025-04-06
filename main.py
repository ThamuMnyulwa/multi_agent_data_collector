"""
Multi-Agent Data Collector for Hotel Information

This script collects hotel information from websites using direct API calls to Firecrawl.
It demonstrates a simplified approach to web scraping for data collection.

Requirements:
- Python 3.9+
- requests
- OpenAI API key (for advanced data extraction - optional)
- CrewAI (for multi-agent orchestration - optional)
- uv (for Python package management)

How to run:
1. Set environment variables:
   export FIRECRAWL_API_KEY="your_firecrawl_api_key"  # Required for API access
   export OPENAI_API_KEY="your_openai_api_key"  # Required for hotel URL generation

2. Run with UV:
   a. Standard mode: uv run python3 main.py
   b. CrewAI mode: uv run python3 main.py --crewai
   c. Specify location: uv run python3 main.py --location "New York"
   d. Pre-scrape with hotel_scraper: uv run python3 main.py --use-scraped-data --data-file hotels.json
"""

import os
import json
import time
import random
import re
import requests
import argparse
import subprocess
import traceback
from typing import Dict, List, Any

# Import our hotel URL generator
from app.create_list_of_hotels import get_hotel_urls_with_rate_limiting

# Try to import CrewAI implementation
CREWAI_AVAILABLE = False
try:
    print("Attempting to import CrewAI...")
    import crewai
    from crewai import Agent, Task, Crew, Process

    # Now try to import our crew main function
    print("Importing crew_main from app.hotel_crew...")
    from app.hotel_crew import main as crew_main

    CREWAI_AVAILABLE = True
    print("CrewAI is available and will be used when requested")
except ImportError as e:
    print(f"Error importing CrewAI: {e}")
    traceback.print_exc()
    CREWAI_AVAILABLE = False
    print("CrewAI not available. Install with 'uv add \"crewai[tools]\"'")


def main():
    print("Hello from multi-agent-data-collector!")


# Helper function to handle rate limiting
def handle_rate_limit(func):
    """Decorator to handle rate limiting with exponential backoff."""

    def wrapper(*args, **kwargs):
        max_retries = 5
        retry_delay = 5  # Start with 5 seconds

        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_str = str(e).lower()
                if "rate limit" in error_str or "429" in error_str:
                    wait_time = retry_delay * (2**attempt) + random.uniform(0, 1)
                    print(
                        f"Rate limit hit. Waiting {wait_time:.2f} seconds before retry {attempt+1}/{max_retries}..."
                    )
                    time.sleep(wait_time)
                else:
                    # If it's not a rate limit error, re-raise it
                    raise

        # If we've exhausted all retries
        raise Exception(f"Failed after {max_retries} attempts due to rate limiting")

    return wrapper


# Firecrawl API client for direct interaction
class FirecrawlClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("FIRECRAWL_API_KEY")
        self.base_url = "https://api.firecrawl.dev/v0"

        if not self.api_key:
            print("WARNING: No Firecrawl API key found. API calls may fail.")

    def _get_headers(self):
        """Get the common headers for API requests."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    @handle_rate_limit
    def start_crawl_job(self, url, options=None):
        """Start a crawl job and return the job ID."""
        api_endpoint = f"{self.base_url}/crawl"

        # Default options - more inclusive
        crawl_options = {
            "limit": 20,  # Increased from 10
            # No includes filter to get all URLs
            # We'll filter later in our code
        }

        # Update with custom options if provided
        if options:
            crawl_options.update(options)

        # Print debug info
        print(f"Crawl options: {crawl_options}")

        # Prepare the request
        payload = {"url": url, "options": crawl_options}

        headers = self._get_headers()

        print(f"Starting crawl job for: {url}")

        # Make the request
        response = requests.post(api_endpoint, json=payload, headers=headers)

        # Print response details for debugging
        print(f"Response status code: {response.status_code}")
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            raise Exception(
                f"Crawl API error: {response.status_code} - {response.text}"
            )

        # Handle response
        result = response.json()
        print(f"Response keys: {list(result.keys())}")

        if "jobId" in result:
            job_id = result["jobId"]
            print(f"Crawl job started with ID: {job_id}")
            return job_id
        else:
            raise Exception(f"No job ID returned from crawl API: {result}")

    @handle_rate_limit
    def get_crawl_job_status(self, job_id):
        """Get the status of a crawl job."""
        api_endpoint = f"{self.base_url}/crawl/{job_id}"

        headers = self._get_headers()

        # Make the request
        response = requests.get(api_endpoint, headers=headers)

        # Handle response
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            raise Exception(
                f"Job status API error: {response.status_code} - {response.text}"
            )

    def wait_for_crawl_job(self, job_id, max_retries=20, initial_delay=2):
        """Wait for a crawl job to complete."""
        print(f"Waiting for crawl job {job_id} to complete...")

        retry_count = 0
        delay = initial_delay

        while retry_count < max_retries:
            try:
                # Get the job status
                status = self.get_crawl_job_status(job_id)

                # Check if the job is done
                job_status = status.get("status")
                print(f"Job status: {job_status}")

                if job_status == "completed":
                    print("Job completed successfully!")
                    return status
                elif job_status == "failed":
                    raise Exception(
                        f"Crawl job failed: {status.get('error', 'Unknown error')}"
                    )
                elif job_status == "processing" or job_status == "queued":
                    # Job is still running, wait and try again
                    print(f"Job is {job_status}, waiting {delay} seconds...")
                    time.sleep(delay)
                    delay = min(delay * 1.5, 10)  # Increase delay, but max 10 seconds
                    retry_count += 1
                else:
                    raise Exception(f"Unknown job status: {job_status}")

            except Exception as e:
                print(f"Error checking job status: {e}")
                retry_count += 1
                time.sleep(delay)

        raise Exception(f"Timed out waiting for crawl job {job_id} to complete")

    @handle_rate_limit
    def crawl_website(self, url, options=None):
        """Crawl a website and wait for results."""
        # Start the crawl job
        job_id = self.start_crawl_job(url, options)

        # Wait for the job to complete
        result = self.wait_for_crawl_job(job_id)

        # Extract the URLs from the result
        return result

    @handle_rate_limit
    def scrape_website(self, url):
        """Scrape a website and return its content."""
        api_endpoint = f"{self.base_url}/scrape"

        # Prepare the request
        payload = {"url": url}
        headers = self._get_headers()

        print(f"Making scrape request for URL: {url}")

        # Make the request
        response = requests.post(api_endpoint, json=payload, headers=headers)

        # Print response details for debugging
        print(f"Scrape response status code: {response.status_code}")

        # Handle response
        if response.status_code == 200:
            result = response.json()
            print(f"Scrape response keys: {list(result.keys())}")

            # Extract the data from the result
            if "data" in result:
                # The actual content is in the data key
                return result["data"]
            else:
                return result
        else:
            raise Exception(
                f"Scrape API error: {response.status_code} - {response.text}"
            )


# Simple class to collect hotel URLs
class HotelURLCollector:
    def __init__(self, start_url, client=None, location="worldwide", num_hotels=10):
        self.start_url = start_url
        self.client = client or FirecrawlClient()
        self.location = location
        self.num_hotels = num_hotels

    def collect_urls(self):
        """Collect hotel URLs from the starting page."""
        print(f"Collecting URLs from: {self.start_url}")
        try:
            # Call the Firecrawl API to crawl the website
            result = self.client.crawl_website(
                self.start_url,
                options={
                    # Get all URLs, no filtering at the API level
                    "limit": 20
                },
            )

            # Extract URLs from the response
            urls = []

            # Check different possible formats of the result
            if "pages" in result:
                print(f"Found {len(result['pages'])} pages in the crawl result")

                # Extract URLs from the crawl result
                for i, page in enumerate(result["pages"]):
                    if "url" in page:
                        page_url = page["url"]
                        print(f"Found URL {i+1}: {page_url}")

                        # Filter for hotel URLs at the code level
                        if "/hotel" in page_url.lower() or "hotel" in page_url.lower():
                            urls.append(page_url)
                            print(f"  ✓ Added as hotel URL")
                        else:
                            print(f"  ✗ Not a hotel URL, skipping")

            # If we found no URLs through the standard format, try to look in other places
            if not urls and "data" in result:
                print("Found 'data' key, examining its contents...")
                data = result["data"]

                if isinstance(data, list):
                    print(f"Data is a list with {len(data)} items")
                    for item in data:
                        if isinstance(item, dict) and "url" in item:
                            url = item["url"]
                            if "/hotel" in url.lower() or "hotel" in url.lower():
                                urls.append(url)
                                print(f"Found hotel URL in data: {url}")
                elif isinstance(data, dict) and "urls" in data:
                    print("Data contains a 'urls' key")
                    for url in data["urls"]:
                        if "/hotel" in url.lower() or "hotel" in url.lower():
                            urls.append(url)
                            print(f"Found hotel URL in data.urls: {url}")

            # If we still found no URLs, try to search for them in the raw response
            if not urls:
                print(
                    "No URLs found through structured parsing, searching in raw response"
                )
                raw_urls = re.findall(r"https?://[^\s\"\']+", json.dumps(result))

                # Filter for likely hotel URLs
                for url in raw_urls:
                    if "/hotel" in url.lower() or "hotel" in url.lower():
                        urls.append(url)
                        print(f"Found in raw text: {url}")

            if not urls:
                # If no URLs found, use OpenAI to generate hotel URLs
                print(
                    f"No hotel URLs found. Using OpenAI to generate hotel URLs for {self.location}..."
                )

                # Get hotel info from our generator
                hotel_data = get_hotel_urls_with_rate_limiting(
                    self.location, self.num_hotels
                )

                # Extract just the URLs
                urls = [hotel["url"] for hotel in hotel_data]

                print(f"Generated {len(urls)} hotel URLs using OpenAI:")
                for i, url in enumerate(urls):
                    print(f"  {i+1}. {url}")

            print(f"Found {len(urls)} hotel URLs.")
            return urls

        except Exception as e:
            print(f"Error collecting URLs: {e}")
            import traceback

            traceback.print_exc()

            # Fallback to OpenAI generated URLs if there's an error
            print("Error occurred. Using OpenAI to generate hotel URLs.")
            hotel_data = get_hotel_urls_with_rate_limiting(
                self.location, self.num_hotels
            )
            urls = [hotel["url"] for hotel in hotel_data]
            return urls


# Simple class to scrape hotel details
class HotelScraper:
    def __init__(self, hotel_url, client=None):
        self.hotel_url = hotel_url
        self.client = client or FirecrawlClient()

    def scrape(self):
        """Scrape details from a hotel page."""
        print(f"Scraping details from: {self.hotel_url}")
        try:
            # Call the Firecrawl API to scrape the website
            result = self.client.scrape_website(self.hotel_url)

            if not result:
                print(f"Failed to scrape information from {self.hotel_url}")
                return None

            # Extract content from the result based on the data format
            content = ""
            title = ""
            description = ""

            # Try different possible formats of the result
            if isinstance(result, dict):
                # If result is already a dict, look for content fields
                content = result.get("content", "")
                title = result.get("title", "")
                description = result.get("description", "")

                # If no content found, try check 'text' and 'markdown' fields
                if not content:
                    content = result.get("text", result.get("markdown", ""))

            # If no title was found, extract it from the URL
            if not title:
                title = self._extract_title_from_url(self.hotel_url)

            # Extract essential information
            hotel_info = {
                "hotel_name": title or "Unknown Hotel",
                "description": description or "No description available",
                "url": self.hotel_url,
                "address": self._extract_address(content),
                "price": self._extract_price(content),
            }

            # Print what we found for debugging
            print(f"Extracted hotel_name: {hotel_info['hotel_name']}")
            print(f"Extracted address: {hotel_info['address']}")
            print(f"Extracted price: {hotel_info['price']}")

            return hotel_info

        except Exception as e:
            print(f"Error scraping {self.hotel_url}: {e}")
            import traceback

            traceback.print_exc()

            # Return a minimal object with the URL at least
            return {
                "hotel_name": self._extract_title_from_url(self.hotel_url),
                "description": "Error occurred during scraping",
                "url": self.hotel_url,
                "address": "Error retrieving address",
                "price": "Error retrieving price",
            }

    def _extract_title_from_url(self, url):
        """Extract a title from the URL as a fallback."""
        try:
            # Try to extract the hotel name from the URL
            # Example: https://www.booking.com/hotel/us/the-plaza.html -> The Plaza
            parts = url.split("/")
            if len(parts) >= 2:
                name_part = parts[-1] if parts[-1] != "" else parts[-2]
                name_part = name_part.split(".")[0]  # Remove file extension
                name_part = name_part.replace("-", " ").replace("_", " ")

                # Title case and clean up
                name = " ".join([w.capitalize() for w in name_part.split()])

                if name:
                    return name

            # If we get here, use the domain as fallback
            domain = re.search(r"https?://(?:www\.)?([^/]+)", url)
            if domain:
                return f"Hotel from {domain.group(1)}"

            return "Unknown Hotel"
        except:
            return "Unknown Hotel"

    def _extract_address(self, content):
        """Extract address from scraping result."""
        if not content:
            return "Address not found"

        # Look for content that might contain an address
        address_patterns = [
            r"(?i)address:\s*([^,\n]+(?:,\s*[^,\n]+){1,3})",
            r"(?i)location:\s*([^,\n]+(?:,\s*[^,\n]+){1,3})",
            r"(?i)(?:hotel|property) address[:\s]+([^,\n]+(?:,\s*[^,\n]+){1,3})",
        ]

        for pattern in address_patterns:
            matches = re.findall(pattern, content)
            if matches:
                return matches[0]

        return "Address not found"

    def _extract_price(self, content):
        """Extract price from scraping result."""
        if not content:
            return "Price not found"

        # Look for price patterns
        price_patterns = [
            r"(?i)price:\s*(\$[\d,]+(?:\.\d{2})?)",
            r"(?i)(?:USD|EUR|GBP)\s*([\d,]+(?:\.\d{2})?)",
            r"(?i)(\$[\d,]+(?:\.\d{2})?)\s*per night",
            r"(?i)(?:rate|room rate)[:\s]+(\$[\d,]+(?:\.\d{2})?)",
            r"(?i)(\$[\d,]+(?:\.\d{2})?)",
        ]

        for pattern in price_patterns:
            matches = re.findall(pattern, content)
            if matches:
                return matches[0]

        return "Price not found"


# Main data collection handler
class HotelDataCollector:
    def __init__(
        self, start_url, location="worldwide", num_hotels=10, scraped_data=None
    ):
        self.start_url = start_url
        self.location = location
        self.num_hotels = num_hotels
        self.client = FirecrawlClient()
        self.url_collector = HotelURLCollector(
            start_url, self.client, location, num_hotels
        )
        self.results = []
        self.scraped_data = scraped_data  # Pre-scraped data from hotel_scraper.py

    def collect_data(self):
        """Collect hotel data from the starting URL or use pre-scraped data."""
        try:
            # If we have pre-scraped data, use it instead of collecting new URLs
            if self.scraped_data:
                print(f"Using {len(self.scraped_data)} pre-scraped hotel entries")
                hotel_urls = [
                    hotel["url"] for hotel in self.scraped_data if hotel.get("url")
                ]

                # Initialize results with the pre-scraped data
                self.results = self.scraped_data.copy()

                print(f"Found {len(hotel_urls)} valid hotel URLs in pre-scraped data")
                return self.results

            # Step 1: Collect hotel URLs
            print("Step 1: Collecting hotel URLs...")
            hotel_urls = self.url_collector.collect_urls()

            if not hotel_urls:
                print(
                    "No hotel URLs found. Try using a different location or search term."
                )
                return []

            # Limit to 3 URLs to avoid rate limiting during testing
            hotel_urls = hotel_urls[:3]
            print(
                f"Processing only the first {len(hotel_urls)} URLs to avoid rate limiting."
            )

            # Step 2: Process each hotel URL with delays between requests
            print("\nStep 2: Processing each hotel URL...")
            for i, hotel_url in enumerate(hotel_urls):
                print(f"\nProcessing URL {i+1}/{len(hotel_urls)}: {hotel_url}")

                # Add a delay between requests to avoid rate limiting
                if i > 0:
                    wait_time = random.uniform(3, 7)  # Random delay between 3-7 seconds
                    print(f"Waiting {wait_time:.2f} seconds before next request...")
                    time.sleep(wait_time)

                # Create a scraper for this URL
                scraper = HotelScraper(hotel_url, self.client)

                # Scrape the hotel details
                hotel_info = scraper.scrape()

                if hotel_info:
                    # Validate the data
                    if self._validate_hotel_info(hotel_info):
                        self.results.append(hotel_info)
                        print(f"Successfully processed {hotel_url}")
                    else:
                        print(f"Validation failed for {hotel_url}")

            return self.results

        except Exception as e:
            print(f"Error collecting data: {e}")
            import traceback

            traceback.print_exc()
            return []

    def _validate_hotel_info(self, hotel_info):
        """Validate that hotel info contains required fields."""
        required_fields = ["hotel_name", "url"]  # Reduced requirements
        for field in required_fields:
            if field not in hotel_info or not hotel_info[field]:
                print(f"Missing or empty field: {field}")
                return False
        return True


def run_hotel_scraper(location, output_file, count=10):
    """Run the hotel_scraper.py script to collect initial hotel data."""
    print(f"Running hotel_scraper.py to collect data for {location}...")

    try:
        cmd = [
            "uv",
            "run",
            "python",
            "hotel_scraper.py",
            "--location",
            location,
            "--count",
            str(count),
            "--output",
            output_file,
        ]

        process = subprocess.run(cmd, check=True, text=True, capture_output=True)

        print(process.stdout)

        if process.returncode == 0:
            print(f"Successfully collected data and saved to {output_file}")
            return True
        else:
            print(f"Error running hotel_scraper.py: {process.stderr}")
            return False

    except Exception as e:
        print(f"Error running hotel_scraper.py: {e}")
        return False


def load_scraped_data(file_path):
    """Load pre-scraped hotel data from a JSON file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"Loaded {len(data)} hotels from {file_path}")
        return data
    except Exception as e:
        print(f"Error loading scraped data from {file_path}: {e}")
        return []


def run_standard_mode(
    location, start_url, use_scraped_data=False, data_file="hotels.json"
):
    """Run the standard (non-CrewAI) data collection process."""

    scraped_data = None

    # If requested, first make sure we have scraped data
    if use_scraped_data:
        # Try to load existing data file
        if os.path.exists(data_file):
            scraped_data = load_scraped_data(data_file)

        # If no data or file doesn't exist, run the scraper
        if not scraped_data:
            success = run_hotel_scraper(location, data_file)
            if success:
                scraped_data = load_scraped_data(data_file)

    # Create the data collector with the scraped data if available
    collector = HotelDataCollector(
        start_url, location=location, num_hotels=5, scraped_data=scraped_data
    )

    # Collect the data
    hotel_results = collector.collect_data()

    # Print the results
    print("\nData collection completed. Final Results:")
    for i, res in enumerate(hotel_results, 1):
        print(f"\nHotel {i}:")
        for key, value in res.items():
            print(f"  {key}: {value}")

    return hotel_results


def run_crewai_mode(
    location, start_url, use_scraped_data=False, data_file="hotels.json"
):
    """Run the CrewAI-based data collection process."""
    if not CREWAI_AVAILABLE:
        print(
            "CrewAI is not available. Please install it with 'uv add \"crewai[tools]\"'"
        )
        return None

    # If using scraped data, load it first
    hotel_urls = []
    if use_scraped_data:
        # Try to load existing data file
        if os.path.exists(data_file):
            scraped_data = load_scraped_data(data_file)
            if scraped_data:
                # Extract URLs from the scraped data
                hotel_urls = [
                    hotel.get("url") for hotel in scraped_data if hotel.get("url")
                ]
                print(f"Using {len(hotel_urls)} pre-scraped hotel URLs with CrewAI")

        # If no data or file doesn't exist, run the scraper
        if not hotel_urls:
            success = run_hotel_scraper(location, data_file)
            if success:
                scraped_data = load_scraped_data(data_file)
                hotel_urls = [
                    hotel.get("url") for hotel in scraped_data if hotel.get("url")
                ]

    print(f"\nStarting CrewAI execution for location: {location}")
    print(f"Using {len(hotel_urls) if hotel_urls else 0} pre-scraped URLs")

    try:
        # Use our CrewAI implementation with the pre-scraped URLs if available
        result = crew_main(start_url, location, hotel_urls)

        # Process and display the result
        print("\n" + "=" * 50)
        print("CrewAI Execution Results")
        print("=" * 50)

        if result:
            if isinstance(result, dict):
                # Try to display in a structured way
                if "hotels" in result:
                    hotels = result["hotels"]
                    print(f"Found {len(hotels)} hotels:")
                    for i, hotel in enumerate(hotels, 1):
                        print(f"\nHotel {i}:")
                        for key, value in hotel.items():
                            if (
                                key != "description" and value
                            ):  # Skip long descriptions in console output
                                print(f"  {key}: {value}")
                else:
                    # Just show top-level info
                    for key, value in result.items():
                        if isinstance(value, (dict, list)):
                            print(
                                f"{key}: {type(value).__name__} with {len(value)} items"
                            )
                        else:
                            print(f"{key}: {value}")
            else:
                # If it's not a dict, just print directly
                print(result)

            # Save a copy in a standard format
            output_file = f"crewai_results_{location.replace(' ', '_')}.json"
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    if isinstance(result, dict):
                        json.dump(result, indent=2, fp=f, ensure_ascii=False)
                    else:
                        json.dump(
                            {"result": str(result)}, indent=2, fp=f, ensure_ascii=False
                        )
                print(f"\nResults saved to {output_file}")
            except Exception as e:
                print(f"Error saving results: {e}")
        else:
            print("No results returned from CrewAI execution")

        return result
    except Exception as e:
        print(f"Error during CrewAI execution: {e}")
        import traceback

        traceback.print_exc()
        return None


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Hotel Data Collector")

    parser.add_argument(
        "--crewai", action="store_true", help="Use CrewAI for data collection"
    )

    parser.add_argument(
        "--location",
        type=str,
        default="worldwide",
        help="Location to search for hotels (e.g., 'New York', 'Paris')",
    )

    parser.add_argument(
        "--use-scraped-data",
        action="store_true",
        help="Use pre-scraped data from hotel_scraper.py",
    )

    parser.add_argument(
        "--data-file",
        type=str,
        default="hotels.json",
        help="JSON file containing pre-scraped hotel data",
    )

    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()

    # Check for required API keys
    if "FIRECRAWL_API_KEY" not in os.environ:
        print(
            "WARNING: FIRECRAWL_API_KEY not set. Please set it to access the Firecrawl API."
        )
        print("Example: export FIRECRAWL_API_KEY='your_key_here'")
        api_key = input(
            "Enter your Firecrawl API key to continue (or press Enter to use demo mode): "
        )
        if api_key:
            os.environ["FIRECRAWL_API_KEY"] = api_key
        else:
            print("Running in demo mode with limited functionality.")

    if "OPENAI_API_KEY" not in os.environ:
        print(
            "WARNING: OPENAI_API_KEY not set. Please set it to generate hotel URLs when needed."
        )
        print("Example: export OPENAI_API_KEY='your_key_here'")
        api_key = input(
            "Enter your OpenAI API key to continue (or press Enter to use fallback hotels): "
        )
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        else:
            print("OpenAI URL generation will be disabled. Using fallback hotel lists.")

    main()

    print("\nStarting hotel data collection...")

    # Define a starting URL that lists hotels
    start_url = "https://www.top10hotels.com/?ufi=-1287082&gacc=gmcc&gad_source=1"

    # Get location from command line arguments or prompt if not provided
    location = args.location
    if not args.location and not args.crewai:
        location = input(
            "Enter a location to search for hotels (e.g., 'New York', 'Paris', or press Enter for worldwide): "
        )
        if not location:
            location = "worldwide"

    print(f"Searching for hotels in: {location}")

    # Run in the appropriate mode
    if args.crewai:
        print("Running in CrewAI mode...")
        run_crewai_mode(location, start_url, args.use_scraped_data, args.data_file)
    else:
        print("Running in standard mode...")
        run_standard_mode(location, start_url, args.use_scraped_data, args.data_file)
