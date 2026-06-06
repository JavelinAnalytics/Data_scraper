# Betting Scraper

## Overview
This project retrieves NBA betting odds using API endpoints.

## Features
- Fetches events from /GetGroup
- Extracts player prop markets
- Builds event configurations
- Polls /GetEventsWithMultipleMarkets
- Parses odds into structured data classes

## Requirements
- Python 3.11 or newer
- pip

## Installation
1. Clone or download the project folder
2. Open an IDE, Create a virtual environment if not automatic:
```bash
python -m venv .venv
```
3. Activate the virtual environment:
Windows:
```bash
.venv\Scripts\activate
```
Linux/MacOS:
```bash
source .venv/bin/activate
```
4. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage
Run the main script:
```bash
python main.py
```

## Project Structure
```text
Betting_Scraper/
├── main.py # Core application logic
├── config.py # Configuration and constants
├── requirements.txt # Project dependencies
├── README.md # Project documentation
├── .gitignore # Ignored files and folders
├── output/ # Optional raw JSON outputs (if enabled)
```

## Workflow
1. Fetch events using `/GetGroup`
2. Extract event IDs
3. Retrieve event details using `/GetEventDetails`
4. Extract player prop markets
5. Build valid event configurations
6. Poll `/GetEventsWithMultipleMarkets`
7. Parse and structure odds data into classes

## Error Handling
- Strict validation for high-level API structures
  - Raises exceptions when critical data is missing or malformed
  - Prevents invalid responses from propagating through the system
- Defensive parsing for lower-level data structures
  - Skips invalid or incomplete entries instead of failing the entire process
  - Ensures partial but usable data can still be returned
- Request timeouts prevent hanging http requests
- Failure tracking with cooldown logic to avoid rate limiting

## Configuration
All configurable parameters are located in `config.py`, including:
- API endpoints, base http request headers/defaults
- Raw JSON response output toggle:
```python
SAVE_RAW_RESPONSES = True
```

## Output
- Parsed match and odds data are printed to the console
- Optional raw API responses are saved as JSON files in the output/ directory






