def main():
    print("Hello from multi-agent-data-collector!")


from crewai import Agent, Crew
from crewai_tools import FirecrawlScrapeWebsiteTool, FirecrawlCrawlWebsiteTool


# URL Collector Agent: Automatically extracts hotel URLs from a starting page.
class URLCollectorAgent(Agent):
    def __init__(self, start_url):
        self.start_url = start_url
        # Configure the crawler tool with options to include only hotel-related URLs.
        self.tool = FirecrawlCrawlWebsiteTool(
            url=start_url,
            crawler_options={
                "includes": ["/hotel"],  # Adjust based on URL patterns for hotels.
                "limit": 50,
            },
        )

    def run(self):
        # Crawl the website to get a list of URLs.
        result = (
            self.tool.crawl()
        )  # Assumes the tool returns a dict with key "data" containing URLs.
        urls = result.get("data", [])
        print(f"URLCollectorAgent found {len(urls)} URLs.")
        return urls


# Scraper Agent: Scrapes individual hotel pages.
class ScraperAgent(Agent):
    def __init__(self, hotel_url):
        self.hotel_url = hotel_url
        self.tool = FirecrawlScrapeWebsiteTool(url=hotel_url)

    def run(self):
        result = self.tool.scrape()
        print(f"ScraperAgent processed: {self.hotel_url}")
        return result


# Supervisor Agent: Delegates URLs, monitors scraper output, and restarts scraper if needed.
class SupervisorAgent(Agent):
    def __init__(self, hotel_list):
        self.hotel_list = hotel_list
        self.current_index = 0

    def delegate(self):
        if self.current_index < len(self.hotel_list):
            url = self.hotel_list[self.current_index]
            self.current_index += 1
            return url
        else:
            return None

    def monitor(self, scraper_result):
        # Basic check: ensure result is not empty and contains the key "hotel_name"
        if not scraper_result or "hotel_name" not in scraper_result:
            print("SupervisorAgent detected an issue with scraper output.")
            return False
        return True

    def restart_scraper(self, hotel_url):
        print(f"Restarting scraper for {hotel_url}")
        new_scraper = ScraperAgent(hotel_url)
        return new_scraper.run()


# Validator Agent: Validates that scraped data contains required fields.
class ValidatorAgent(Agent):
    def validate(self, data):
        required_fields = ["hotel_name", "address", "price"]
        for field in required_fields:
            if field not in data:
                print(f"ValidatorAgent: Missing field '{field}' in data.")
                return False
        return True


# HotelScrapingCrew: Orchestrates the multi-agent process.
class HotelScrapingCrew(Crew):
    def __init__(self, start_url):
        self.url_collector = URLCollectorAgent(start_url)
        self.results = []

    def kickoff(self):
        # Step 1: Automatically collect hotel URLs.
        hotel_urls = self.url_collector.run()
        if not hotel_urls:
            print("No hotel URLs found.")
            return []
        supervisor = SupervisorAgent(hotel_urls)
        validator = ValidatorAgent()

        # Step 2: Process each hotel URL.
        while True:
            hotel_url = supervisor.delegate()
            if hotel_url is None:
                break  # All URLs processed.
            scraper = ScraperAgent(hotel_url)
            result = scraper.run()
            if not supervisor.monitor(result):
                result = supervisor.restart_scraper(hotel_url)
            if validator.validate(result):
                self.results.append(result)
            else:
                print(f"Validation failed for {hotel_url}")
        return self.results


if __name__ == "__main__":

    main()

    # Define a starting URL that lists hotels.
    # start_url = "https://example.com/hotels"
    start_url = "https://www.top10hotels.com/?ufi=-1287082&gacc=gmcc&gad_source=1"
    crew = HotelScrapingCrew(start_url)
    final_results = crew.kickoff()
    print("\nScraping completed. Final Results:")
    for res in final_results:
        print(res)
