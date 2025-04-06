# multi_agent_data_collector
This repo is to create a multi-agent system that collects data. The idea is to try and play with these systems and see how they work. Preferably trying to use crew AI in the process. 



**Learnings**:
* Crew AI is actually built on of Lang chain. It's one of the dependencies. Lang chain and Lang Graph are lower level whereas Crew AI is a higher level abstraction.
Below is an implementation that incorporates a **URL Collector Agent** into the system. This new agent automatically gathers initial hotel URLs from a starting page (such as a hotels directory) using Firecrawl’s crawling tool. The complete architecture now includes:

1. **URLCollectorAgent:** Automatically crawls a starting page to extract hotel URLs.
2. **ScraperAgent:** Uses Firecrawl’s scraping tool to scrape details from each hotel URL.
3. **SupervisorAgent:** Delegates URLs to the scraper one at a time, monitors for potential issues (such as missing expected fields), and can restart the scraper if needed.
4. **ValidatorAgent:** Verifies that each scraped result contains essential fields like hotel name, address, and price.
5. **HotelScrapingCrew:** Orchestrates the overall process using the agents above.

---

### Explanation

- **URLCollectorAgent:** Uses the `FirecrawlCrawlWebsiteTool` to automatically collect hotel URLs from a designated start page.  
- **ScraperAgent:** Processes each individual URL using `FirecrawlScrapeWebsiteTool` to extract hotel details.  
- **SupervisorAgent:** Manages the list of URLs by delegating one at a time and monitors the scraper’s output. If the output is missing key fields (e.g., `"hotel_name"`), it restarts the scraper for that URL.  
- **ValidatorAgent:** Ensures the final output has the required fields (`"hotel_name"`, `"address"`, and `"price"`).  
- **HotelScrapingCrew:** Orchestrates the complete workflow by first collecting URLs, then iterating through them with supervision and validation.

### Required Packages

To run this system, you’ll need to add the following packages to your requirements:

- **crewai** (and optionally **crewai[tools]** for the additional tools integration)  
- **firecrawl-py** (for accessing Firecrawl's tools)  
- **requests** (if not already installed, as it may be used internally by these tools)

Your `requirements.txt` might include:

```
crewai[tools]
firecrawl-py
requests
```

For more detailed information on the Firecrawl tools, see the Firecrawl documentation citeturn0search2, and for insights on agent orchestration with CrewAI, refer to the CrewAI agents docs citeturn0search9.

This setup should provide you with a fully autonomous system that not only collects URLs but also processes and validates hotel data seamlessly.