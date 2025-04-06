"""
CrewAI-based Hotel Data Collection System

This module implements a multi-agent system using CrewAI to collect hotel information.
It includes specialized agents for collecting URLs, scraping data, supervising the process,
and validating the collected information.
"""

import os
import json
import datetime
import time
from typing import List, Dict, Any, Optional, Callable, Any
from crewai import Agent, Task, Crew, Process
from crewai_tools import (
    FirecrawlCrawlWebsiteTool,
    FirecrawlScrapeWebsiteTool,
    CodeInterpreterTool,
)

from app.create_list_of_hotels import get_hotel_urls_with_rate_limiting


# Simple custom tool class for our OpenAI hotel URL generator
class CustomTool:
    def __init__(self, name: str, description: str, func: Callable):
        self.name = name
        self.description = description
        self._func = func

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)


def create_url_collector_agent() -> Agent:
    """Create an agent that collects hotel URLs."""
    # Create tools with the correct API key
    firecrawl_api_key = os.environ.get("FIRECRAWL_API_KEY")

    # Create a FirecrawlCrawlWebsiteTool with proper error handling
    firecrawl_crawl_tool = FirecrawlCrawlWebsiteTool(api_key=firecrawl_api_key)

    # Create a code interpreter tool that can call our hotel URL generator
    code_tool = CodeInterpreterTool(
        description="""Generate hotel URLs using OpenAI when no URLs are found via crawling.
        
        You can use the following code as an example:
        ```python
        from app.create_list_of_hotels import get_hotel_urls_with_rate_limiting
        
        # Generate hotel URLs for the location
        try:
            hotels = get_hotel_urls_with_rate_limiting(location, 5)
            urls = [hotel["url"] for hotel in hotels]
            return urls
        except Exception as e:
            print(f"Error generating URLs: {e}")
            return ["https://www.booking.com/hotel/za/the-silo-hotel.html"]
        ```
        """
    )

    tools = [firecrawl_crawl_tool, code_tool]

    return Agent(
        role="URL Collector",
        goal="Find valid hotel URLs from travel websites or generate them if needed",
        backstory="""You are an expert at finding hotel information online.
        Your specialty is identifying valid hotel URLs from travel websites.
        When traditional crawling doesn't yield results, you can generate 
        reliable URLs for well-known hotels.""",
        tools=tools,
        verbose=True,
    )


def create_scraper_agent() -> Agent:
    """Create an agent that scrapes hotel details."""
    # Create tools with the correct API key
    firecrawl_api_key = os.environ.get("FIRECRAWL_API_KEY")

    # Create a FirecrawlScrapeWebsiteTool with proper error handling
    firecrawl_scrape_tool = FirecrawlScrapeWebsiteTool(api_key=firecrawl_api_key)

    tools = [firecrawl_scrape_tool]

    return Agent(
        role="Hotel Scraper",
        goal="Extract detailed information from hotel websites",
        backstory="""You are a skilled web scraper specialized in extracting hotel information.
        You know how to parse hotel websites to find essential details like name, address,
        amenities, and pricing. You are meticulous and ensure you capture all relevant data.""",
        tools=tools,
        verbose=True,
    )


def create_supervisor_agent() -> Agent:
    """Create an agent that supervises the data collection process."""
    return Agent(
        role="Data Collection Supervisor",
        goal="Coordinate the hotel data collection process and ensure quality",
        backstory="""You are a seasoned project manager with expertise in data collection.
        You oversee the entire data collection process, delegating tasks to specialized agents,
        monitoring their progress, and ensuring the data meets quality standards.
        If issues arise, you know how to troubleshoot and reassign tasks.""",
        verbose=True,
    )


def create_validator_agent() -> Agent:
    """Create an agent that validates the collected data."""
    return Agent(
        role="Data Validator",
        goal="Ensure the collected hotel data is accurate and complete",
        backstory="""You are a data quality expert with a keen eye for detail.
        Your job is to review hotel data and ensure it contains all required information 
        and is formatted correctly. You flag issues that need attention and provide
        suggestions for improvement.""",
        verbose=True,
    )


def create_url_collection_task(agent: Agent) -> Task:
    """Create a task for collecting hotel URLs."""
    return Task(
        description="""
        Collect URLs for hotels in {location}.
        
        Start by crawling the provided starting URL: {start_url}
        If no hotel URLs are found through crawling, use the code interpreter tool
        to create URLs for well-known hotels in the specified location.
        
        Return a list of valid hotel URLs (maximum 5 URLs).
        """,
        expected_output="A list of valid hotel URLs (maximum 5 URLs)",
        agent=agent,
    )


def create_scraping_task(agent: Agent) -> Task:
    """Create a task for scraping hotel details."""
    return Task(
        description="""
        Scrape detailed information from the hotel URL provided by the URL collector.
        
        Extract the following information:
        1. Hotel name
        2. Description
        3. Address
        4. Price information
        
        Return the data in a structured JSON format.
        """,
        expected_output="A JSON object containing hotel details",
        agent=agent,
    )


def create_supervision_task(agent: Agent) -> Task:
    """Create a task for supervising the data collection process."""
    return Task(
        description="""
        Supervise the collection of hotel data from multiple URLs.
        
        URL_SOURCE: You will either get URLs from the URL collector agent or they will be provided directly.
        If URLs are provided in the context as {hotel_urls}, use those directly.
        
        1. For each URL in the list provided:
           a. Assign the URL to the scraper
           b. Monitor the scraping results
           c. If any essential fields are missing, request a retry
        
        2. If URLs are not available or the tools fail, use these fallback URLs: {fallback_hotels}
        
        3. Compile all successful results into a single dataset
        
        Return the compiled dataset of hotel information.
        """,
        expected_output="A compiled dataset of hotel information",
        agent=agent,
    )


def create_validation_task(agent: Agent) -> Task:
    """Create a task for validating the collected data."""
    return Task(
        description="""
        Validate the collected hotel data.
        
        For each hotel in the dataset from the supervisor:
        1. Verify that all required fields are present:
           - hotel_name
           - url
           - address
        
        2. Flag any missing or suspicious data
        
        3. For hotels with valid data, assign a quality score from 1-10
        
        Return the validated dataset with quality scores and any flags.
        """,
        expected_output="A validated dataset with quality scores",
        agent=agent,
    )


class HotelScrapingCrew:
    """Crew to orchestrate the hotel data collection process."""

    def __init__(self, start_url: str, location: str = "worldwide"):
        """Initialize the crew with a starting URL and location."""
        self.start_url = start_url
        self.location = location

        # Create agents
        self.url_collector = create_url_collector_agent()
        self.scraper = create_scraper_agent()
        self.supervisor = create_supervisor_agent()
        self.validator = create_validator_agent()

        # Create tasks
        self.url_collection_task = create_url_collection_task(self.url_collector)
        self.scraping_task = create_scraping_task(self.scraper)
        self.supervision_task = create_supervision_task(self.supervisor)
        self.validation_task = create_validation_task(self.validator)

    def run(self, pre_scraped_urls: List[str] = None) -> Dict[str, Any]:
        """Run the hotel data collection process."""
        print(
            f"Starting hotel data collection for {self.location} from {self.start_url}"
        )

        # Create the crew
        crew = Crew(
            agents=[
                self.url_collector,
                self.scraper,
                self.supervisor,
                self.validator,
            ],
            tasks=[
                self.url_collection_task,
                self.scraping_task,
                self.supervision_task,
                self.validation_task,
            ],
            verbose=True,
            process=Process.sequential,  # Use sequential to ensure proper flow
        )

        # Create context for the crew
        crew_context = {
            "start_url": self.start_url,
            "location": self.location,
        }

        # Add fallback hotels to the context
        fallback_hotels = [
            "https://www.booking.com/hotel/za/the-silo-hotel.html",
            "https://www.booking.com/hotel/za/belmond-mount-nelson.html",
            "https://www.booking.com/hotel/za/cape-grace.html",
        ]
        crew_context["fallback_hotels"] = fallback_hotels

        # If pre-scraped URLs are provided, we'll need to handle them in the supervision task
        if pre_scraped_urls:
            print(f"Using {len(pre_scraped_urls)} pre-scraped URLs with CrewAI")

            # Create a simplified version that won't rely on task description modification
            # Just add the URLs directly to the context
            crew_context["hotel_urls"] = pre_scraped_urls

            # For backward compatibility, still try to modify task descriptions
            for task in crew.tasks:
                if "Supervise the collection of hotel data" in task.description:
                    try:
                        # Store URLs for use in supervision task
                        self.hotel_urls = pre_scraped_urls

                        # Modify the task description to use pre-scraped URLs
                        task.description = task.description.replace(
                            "URL_SOURCE: You will either get URLs from the URL collector agent or they will be provided directly.",
                            f"URL_SOURCE: Use these pre-scraped URLs: {pre_scraped_urls[:3]}... (total: {len(pre_scraped_urls)})",
                        )
                    except Exception as e:
                        print(f"Warning: Could not modify task description: {e}")
                    break

        try:
            # Run the crew with a timeout
            print("Starting CrewAI execution...")
            result = crew.kickoff(inputs=crew_context)
            print("CrewAI execution completed")

            # Detailed result logging
            print(f"Raw result type: {type(result)}")
            if isinstance(result, str):
                print(f"Result length: {len(result)}")
                preview = result[:200] if len(result) > 200 else result
                print(f"Result preview: {preview}...")
            elif isinstance(result, dict):
                print(f"Result keys: {list(result.keys())}")
            elif isinstance(result, list):
                print(f"Result length: {len(result)}")
            else:
                print(f"Unexpected result type: {type(result)}")

            # If we have no real result, create a fallback
            if not result:
                print("WARNING: Empty result received from CrewAI, creating fallback")
                # Create a basic structure from pre-scraped URLs if available
                if pre_scraped_urls:
                    result = {"hotels": []}
                    for url in pre_scraped_urls:
                        hotel_name = (
                            url.split("/")[-1]
                            .replace(".html", "")
                            .replace("-", " ")
                            .title()
                        )
                        result["hotels"].append(
                            {
                                "name": hotel_name,
                                "url": url,
                                "note": "This is fallback data as CrewAI returned empty results",
                            }
                        )
                else:
                    result = {
                        "status": "completed",
                        "warning": "No data was returned by the crew",
                        "timestamp": str(datetime.datetime.now()),
                    }

            # Process the result based on its type
            if isinstance(result, str):
                try:
                    # Try to parse JSON string
                    json_result = json.loads(result)
                    print("Successfully parsed string result as JSON")
                    result = json_result
                except json.JSONDecodeError:
                    # If not valid JSON, wrap in a dict
                    print("Result is not valid JSON, wrapping in dictionary")
                    result = {"raw_output": result}

            # Save results to a file with error handling
            try:
                output_file = "crewai_results.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, indent=2, fp=f, ensure_ascii=False)
                print(f"Results saved to {output_file}")

                # Also save a backup copy
                backup_file = f"crewai_results_{int(time.time())}.json"
                with open(backup_file, "w", encoding="utf-8") as f:
                    json.dump(result, indent=2, fp=f, ensure_ascii=False)
                print(f"Backup saved to {backup_file}")
            except Exception as e:
                print(f"Error saving results to file: {e}")
                # Try saving to an alternative location
                alt_file = "crewai_results_emergency.txt"
                with open(alt_file, "w", encoding="utf-8") as f:
                    f.write(str(result))
                print(f"Emergency backup saved to {alt_file}")

            return result

        except Exception as e:
            print(f"Error during CrewAI execution: {e}")
            import traceback

            traceback.print_exc()

            # Create a fallback result based on pre-scraped URLs if available
            fallback_result = {"status": "error", "error": str(e)}

            if pre_scraped_urls:
                fallback_result["hotels"] = []
                for url in pre_scraped_urls:
                    hotel_name = (
                        url.split("/")[-1]
                        .replace(".html", "")
                        .replace("-", " ")
                        .title()
                    )
                    fallback_result["hotels"].append(
                        {
                            "name": hotel_name,
                            "url": url,
                            "note": "This is fallback data due to CrewAI execution error",
                        }
                    )

            fallback_result["timestamp"] = str(datetime.datetime.now())

            # Try to save even the error information
            try:
                error_file = f"crewai_error_{int(time.time())}.json"
                with open(error_file, "w") as f:
                    json.dump(fallback_result, indent=2, fp=f)
                print(f"Error information saved to {error_file}")
            except Exception as save_error:
                print(f"Could not save error information: {save_error}")

            return fallback_result


def main(start_url, location="worldwide", hotel_urls=None):
    """Run the hotel data collection process using CrewAI."""
    print(f"Starting CrewAI-based hotel collection for location: {location}")

    # Display API key information (without revealing the actual keys)
    firecrawl_api_key = os.environ.get("FIRECRAWL_API_KEY", "")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    print(f"FIRECRAWL_API_KEY: {'Set' if firecrawl_api_key else 'Missing'}")
    print(f"OPENAI_API_KEY: {'Set' if openai_api_key else 'Missing'}")

    # Create the crew
    print("Creating CrewAI agent team...")
    crew = HotelScrapingCrew(start_url, location)

    # If we have pre-scraped URLs, display detailed info and use them
    if hotel_urls and isinstance(hotel_urls, list) and len(hotel_urls) > 0:
        print(f"Using {len(hotel_urls)} pre-scraped URLs with CrewAI")
        print("URLs preview:")
        # Show first 3 URLs and count of remaining
        for i, url in enumerate(hotel_urls[:3]):
            print(f"  {i+1}. {url}")
        if len(hotel_urls) > 3:
            print(f"  ...and {len(hotel_urls) - 3} more URLs")

        # Run the crew with the pre-scraped URLs
        print("\nExecuting CrewAI with pre-scraped URLs...")
        result = crew.run(pre_scraped_urls=hotel_urls)
    else:
        # Run the crew normally
        print(
            "\nNo pre-scraped URLs provided, executing CrewAI for URL discovery and scraping..."
        )
        result = crew.run()

    print("\nCrewAI hotel data collection completed!")

    # If result exists, show a summary
    if result:
        # Try to count hotels in the result
        hotel_count = 0
        if isinstance(result, dict):
            if "hotels" in result and isinstance(result["hotels"], list):
                hotel_count = len(result["hotels"])
            elif any(k.startswith("hotel") for k in result.keys()):
                hotel_count = sum(1 for k in result.keys() if k.startswith("hotel"))

        print(f"Retrieved information for approximately {hotel_count} hotels")

        # Show result file locations
        for file in os.listdir("."):
            if file.startswith("crewai_results") and os.path.getsize(file) > 0:
                print(f"Results saved to: {file} ({os.path.getsize(file)} bytes)")
    else:
        print("No results were returned from CrewAI")

    return result


if __name__ == "__main__":
    # Default starting URL
    start_url = "https://www.top10hotels.com/?ufi=-1287082&gacc=gmcc&gad_source=1"

    # Get location from command line arguments
    import sys

    location = sys.argv[1] if len(sys.argv) > 1 else "worldwide"

    main(start_url, location)
