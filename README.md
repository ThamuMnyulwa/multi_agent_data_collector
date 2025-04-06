# Multi-Agent Hotel Data Collector

A collaborative AI system for collecting detailed hotel information using both standard and multi-agent approaches. This project demonstrates how to build scalable data collection systems with CrewAI.

## Features

- Collect hotel URLs from travel websites or generate them using OpenAI
- Scrape detailed information from hotel websites using Firecrawl
- Validate and process collected data for quality assurance
- Support for various locations worldwide with detailed location-specific handling
- Two operating modes:
  - Standard mode (simple sequential processing)
  - CrewAI mode (sophisticated multi-agent collaborative system)
- Fault tolerance and error handling for robust operation
- Support for pre-scraped data to improve performance and reliability

## Getting Started

### Requirements

Make sure you have the following:

- Python 3.12+
- UV package manager (recommended for dependency management)
- Firecrawl API key (for web scraping) - get from [firecrawl.dev](https://firecrawl.dev)
- OpenAI API key (for hotel URL generation and agent intelligence)

### Installation

1. Clone the repository:

2. Set up your environment and install dependencies:
```bash
# Using UV (recommended)
uv init
uv sync
```

3. Set up your environment variables:
```bash
# Add these to your .env file or export directly
export FIRECRAWL_API_KEY="your_firecrawl_api_key"
export OPENAI_API_KEY="your_openai_api_key"
```

## Basic Usage

### Standard Mode

Run the data collector in standard mode:
```bash
uv run python3 main.py
```

### CrewAI Mode (Multi-Agent)

Run with CrewAI mode to use the multi-agent system:
```bash
uv run python3 main.py --crewai
```

### Specify Location

Search for hotels in a specific location:
```bash
uv run python3 main.py --location "Cape Town, South Africa"
```

### Using Pre-Scraped Data

For improved performance and reliability, you can use pre-scraped data:
```bash
# First, collect and save hotel data
uv run python3 hotel_scraper.py --location "Cape Town, South Africa" --count 10 --output capetown_hotels.json

# Then use it with the main program
uv run python3 main.py --crewai --use-scraped-data --data-file capetown_hotels.json --location "Cape Town, South Africa"
```

## Advanced Usage

### Command Line Arguments

The application supports various command line arguments:

| Argument | Description |
|----------|-------------|
| `--crewai` | Run in CrewAI mode (multi-agent system) |
| `--location` | Specify location to search for hotels (e.g., "New York", "Paris") |
| `--use-scraped-data` | Use pre-scraped data from hotel_scraper.py |
| `--data-file` | Specify JSON file containing pre-scraped hotel data |

### Example Use Cases

#### Basic Hotel Information Gathering

```bash
uv run python3 main.py --location "New York"
```

This will:
1. Search for hotels in New York
2. Collect URLs for hotels in the area
3. Scrape basic information from each hotel's website
4. Display and save the results

#### Comprehensive Hotel Analysis with Multi-Agent System

```bash
uv run python3 main.py --crewai --location "Paris, France"
```

This will:
1. Deploy a team of specialized AI agents to collect hotel data
2. The URL Collector agent will find hotel URLs in Paris
3. The Hotel Scraper agent will extract detailed information from each hotel
4. The Data Collection Supervisor will oversee the process and compile results
5. The Data Validator will ensure data quality and assign quality scores
6. Results will be saved to `crewai_results_Paris,_France.json`

#### Efficient Data Collection with Pre-Scraped Data

```bash
# First collect the data
uv run python hotel_scraper.py --location "Tokyo, Japan" --count 15 --output tokyo_hotels.json

# Then process it with the multi-agent system
uv run python main.py --crewai --use-scraped-data --data-file tokyo_hotels.json --location "Tokyo, Japan"
```

This workflow:
1. Pre-collects hotel URLs and basic data for Tokyo
2. Uses the more efficient multi-agent system to process and enhance this data
3. Bypasses the URL collection step, making the process faster and more reliable

## Step-by-Step Demonstration

Here's a complete demonstration of using the system to collect hotel data for Cape Town, South Africa:

### Step 1: Collect Initial Hotel Data

First, we'll use the `hotel_scraper.py` script to collect initial hotel data for Cape Town:

```bash
uv run python hotel_scraper.py --location "Cape Town, South Africa" --count 10 --output capetown_hotels.json
```

This will:
- Connect to the OpenAI API to generate hotel URLs
- Process each URL with Firecrawl to extract basic information
- Save the results to `capetown_hotels.json`

### Step 2: Process with CrewAI Multi-Agent System

Next, we'll use CrewAI to process the pre-scraped data:

```bash
uv run python main.py --crewai --use-scraped-data --data-file capetown_hotels.json --location "Cape Town, South Africa"
```

During execution, you'll see detailed logs of the system's operation:

```
Starting CrewAI-based hotel collection for location: Cape Town, South Africa
FIRECRAWL_API_KEY: Set
OPENAI_API_KEY: Set
Creating CrewAI agent team...
Using 10 pre-scraped URLs with CrewAI
URLs preview:
  1. https://www.booking.com/hotel/za/the-silo-hotel.html
  2. https://www.booking.com/hotel/za/belmond-mount-nelson.html
  3. https://www.booking.com/hotel/za/the-table-bay.html
  ...and 7 more URLs

Executing CrewAI with pre-scraped URLs...
Starting hotel data collection for Cape Town, South Africa from https://www.top10hotels.com/?ufi=-1287082&gacc=gmcc&gad_source=1
Starting CrewAI execution...
```

The system will then:
1. Deploy the URL Collector Agent
2. Deploy the Hotel Scraper Agent
3. Deploy the Data Collection Supervisor
4. Deploy the Data Validator

Each agent will perform its task and provide updates:

```
🚀 Crew: crew
├── 📋 Task: URL Collection
│   └── 🤖 Agent: URL Collector
│       ├── 🔧 Using Firecrawl web crawl tool
│       └── 🔧 Using Code Interpreter
├── 📋 Task: Hotel Scraping
│   └── 🤖 Agent: Hotel Scraper
│       └── 🔧 Using Firecrawl web scrape tool
├── 📋 Task: Data Collection Supervision
│   └── 🤖 Agent: Data Collection Supervisor
└── 📋 Task: Data Validation
    └── 🤖 Agent: Data Validator
```

### Step 3: View Results

When the process completes, you'll receive a validated dataset of hotels:

```json
{
  "validated_hotels": [
    {
      "name": "The Silo Hotel",
      "url": "https://www.booking.com/hotel/za/the-silo-hotel.html",
      "address": "Silo Square, V&A Waterfront, Cape Town, South Africa",
      "quality_score": 10,
      "flag": null
    },
    {
      "name": "Belmond Mount Nelson Hotel",
      "url": "https://www.marriott.com/en-us/hotels/cptjw-jw-marriott-hotel-cape-town/overview/",
      "address": "76 Orange Street, Gardens, Cape Town, South Africa",
      "quality_score": 10,
      "flag": null
    },
    // Additional hotels...
  ]
}
```

The system saves results to `crewai_results_Cape_Town,_South_Africa.json` and provides a summary:

```
CrewAI hotel data collection completed!
Retrieved information for approximately 10 hotels
Results saved to: crewai_results_Cape_Town,_South_Africa.json (2695 bytes)
```

## How It Works

### Standard Mode

1. The `HotelURLCollector` gathers hotel URLs from a starting page
2. If no URLs are found, it uses OpenAI to generate URLs for well-known hotels
3. The `HotelScraper` extracts details from each hotel URL
4. The `HotelDataCollector` coordinates the overall process

### CrewAI Mode (Multi-Agent Architecture)

This implementation uses the CrewAI framework to orchestrate multiple agents working together:

1. **URL Collector Agent**: Finds hotel URLs using Firecrawl's crawling tool and OpenAI
2. **Hotel Scraper Agent**: Extracts detailed hotel information using Firecrawl's scraping tool
3. **Data Collection Supervisor**: Manages the process, delegates tasks, and compiles results
4. **Data Validator**: Ensures data quality, flags issues, and assigns quality scores

## System Architecture

The complete architecture includes:

1. **URL Collector Agent**: Discovers hotel URLs through web crawling or generates them with AI.
2. **Hotel Scraper Agent**: Extracts structured data from hotel websites using specialized tools.
3. **Data Collection Supervisor**: Orchestrates the data collection process, monitors progress, and aggregates results.
4. **Data Validator**: Verifies data quality, identifies missing information, and assigns quality ratings.
5. **HotelScrapingCrew**: Coordinates the entire workflow, manages task delegation, and ensures proper data handling.

The system features robust error handling, fallback mechanisms, and result persistence, ensuring reliable operation even when facing API issues or connectivity problems.

## CrewAI Implementation

The CrewAI implementation in `app/hotel_crew.py` demonstrates how to:

1. Define specialized agents with specific roles and tools
2. Create tasks with clear descriptions and expected outputs
3. Configure agent interactions and workflow
4. Handle errors and provide fallback mechanisms
5. Process and save results effectively

This architecture provides a complete, autonomous system for hotel data collection that combines web crawling, AI-powered content extraction, and quality control.

## Result Format

The application produces structured output in JSON format, for example:

```json
{
  "validated_hotels": [
    {
      "name": "The Silo Hotel",
      "url": "https://www.booking.com/hotel/za/the-silo-hotel.html",
      "address": "Silo Square, V&A Waterfront, Cape Town, South Africa",
      "quality_score": 10,
      "flag": null
    },
    {
      "name": "Belmond Mount Nelson Hotel",
      "url": "https://www.marriott.com/en-us/hotels/cptjw-jw-marriott-hotel-cape-town/overview/",
      "address": "76 Orange Street, Gardens, Cape Town, South Africa",
      "quality_score": 10,
      "flag": null
    }
    // More hotels...
  ]
}
```

## Troubleshooting

### CrewAI Mode Issues

If you encounter the error message "CrewAI not available. Install with 'uv add crewai'", you need to install CrewAI with its full tools package:

```bash
uv add "crewai[tools]"
uv add firecrawl-py
```

### API Keys

If your API keys aren't properly set, you'll be prompted to enter them interactively. For better automation, set them in environment variables:

```bash
export FIRECRAWL_API_KEY="your_firecrawl_api_key"
export OPENAI_API_KEY="your_openai_api_key"
```

### Common Warnings

You may see some Pydantic deprecation warnings related to validators when running the application. These come from the CrewAI tools library and don't affect functionality.

## Learning Insights

* CrewAI is built on top of LangChain and provides a higher-level abstraction for creating multi-agent systems.
* Multi-agent systems excel at complex tasks requiring different expertise areas.
* Proper error handling and fallback mechanisms are essential for robust AI-powered applications.
* Pre-scraped data can significantly improve performance and reliability in production environments.