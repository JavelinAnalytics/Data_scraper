"""
Betway NBA odds scraper and polling system.

This script:
1. Fetches NBA event IDs from /GetGroup
2. Builds event configurations from /GetEventDetails
3. Polls /GetEventsWithMultipleMarkets for live odds updates
4. Parses responses into Match and Odd dataclass objects

"""

import uuid
import requests
import json
import time
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from config import (
    BASE_HEADERS,
    GET_GROUP_DEFAULTS,
    GET_EVENT_DETAILS_DEFAULTS,
    GET_EVENTS_WITH_MULTIPLE_MARKETS_DEFAULTS,
    GET_GROUP_URL,
    GET_EVENT_DETAILS_URL,
    GET_EVENTS_WITH_MULTIPLE_MARKETS_URL,
    REQUEST_TIMEOUT_SECONDS,
    SAVE_RAW_RESPONSES
)


@dataclass
class Odd:
    """
    Represents a single betting outcome.

    Attributes:
        id: Unique identifier for the outcome.
        market: Human-readable market name (Money Line, Total Points - Devin Booker).
        bet_name: Name of the specific betting side (Over, Under, Home, Away).
        american_odds: Odds converted into American format.
    """
    id: str
    market: str
    bet_name: str
    american_odds: int


@dataclass
class Match:
    """
    Represents a single sporting event and its associated odds.

    Attributes:
        id: Unique identifier for the event.
        home_team: Name of the home team.
        away_team: Name of the away team.
        start_time: Event start time, or None if unavailable or invalid.
        sport: Sport category name.
        league: League name.
        odds: List of parsed betting outcomes associated with the event.
    """
    id: str
    home_team: str
    away_team: str
    start_time: Optional[datetime]
    sport: str
    league: str
    odds: List[Odd]


def decimal_to_american(decimal_odds: float) -> int:
    """
    Convert decimal betting odds into American odds format.

    Decimal odds greater than or equal to 2.00 convert to positive American odds.
    Decimal odds between 1.00 and 2.00 convert to negative American odds.

    Args:
        decimal_odds: Odds in decimal format.

    Returns:
        The equivalent American odds as an integer.

    Raises:
        ValueError: If the decimal odds are less than or equal to 1.
    """
    if decimal_odds <= 1:
        raise ValueError("Decimal odds must be greater than 1")

    elif decimal_odds >= 2:
        return int(round((decimal_odds - 1) * 100))

    else:
        return int(round(-100 / (decimal_odds - 1)))


def build_get_group_payload() -> dict:
    """
    Build the JSON payload for the /GetGroup endpoint.

    This endpoint is used to retrieve the available NBA event group data,
    including the list of event IDs.

    Returns:
        A dictionary representing the POST request payload for /GetGroup.
    """
    payload = dict(GET_GROUP_DEFAULTS)
    payload["CorrelationId"] = str(uuid.uuid4())
    return payload


def build_get_event_details_payload(event_id: int) -> dict:
    """
    Build the JSON payload for the /GetEventDetails endpoint.

    This endpoint is used to retrieve detailed market data for a single event,
    including all betting markets for a single event.

    Args:
        event_id: The Betway event ID to request.

    Returns:
        A dictionary representing the POST request payload for /GetEventDetails.
    """
    payload = dict(GET_EVENT_DETAILS_DEFAULTS)
    payload["CorrelationId"] = str(uuid.uuid4())
    payload["EventId"] = event_id
    return payload


def build_headers(header_template: dict, referer: str | None = None) -> dict:
    """
    Build HTTP headers for a Betway API request.

    A fresh correlation ID is added to every request. A referer may also be
    injected dynamically depending on the endpoint being called.

    Args:
        header_template: Base header dictionary imported from config.py.
        referer: Optional referer URL to attach to the request.

    Returns:
        A dictionary containing the final headers for the request.
    """
    headers = dict(header_template)
    headers["X-Correlation-Id"] = str(uuid.uuid4())

    if referer is not None:
        headers["Referer"] = referer

    return headers


def post_json(url: str, headers: dict, payload: dict) -> dict:
    """
    Send a POST request and return the parsed JSON response.

    This is the generic low-level request function used by all endpoint-specific
    fetch functions in the scraper.

    Args:
        url: The endpoint URL.
        headers: Request headers for the endpoint.
        payload: JSON payload to send in the POST body.

    Returns:
        The parsed JSON response as a dictionary.

    Raises:
        requests.HTTPError: If the response status indicates an HTTP failure.
    """
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def fetch_get_group_data() -> dict:
    """
    Fetch raw event group data from the /GetGroup endpoint.

    This request is used as the first discovery step in the workflow to obtain
    candidate NBA event IDs.

    Returns:
        The parsed JSON response from /GetGroup.
    """
    payload = build_get_group_payload()
    referer = "https://betway.com/gb/en/sports/grp/basketball/usa/nba"
    headers = build_headers(BASE_HEADERS, referer=referer)
    return post_json(GET_GROUP_URL, headers, payload)


def fetch_get_event_details(event_id: int) -> dict:
    """
    Fetch detailed event market data from the /GetEventDetails endpoint.

    This request is used to inspect a single event and extract the player prop
    market identifiers needed for later polling.

    Args:
        event_id: The Betway event ID to inspect.

    Returns:
        The parsed JSON response from /GetEventDetails.
    """
    payload = build_get_event_details_payload(event_id)
    referer = f"https://betway.com/gb/en/sports/event/{event_id}"
    headers = build_headers(BASE_HEADERS, referer=referer)
    return post_json(GET_EVENT_DETAILS_URL, headers, payload)


def extract_event_ids(get_group_data: dict) -> list[int]:
    """
    Extract all event IDs from the /GetGroup response.

    The /GetGroup endpoint returns a nested structure where event IDs are stored
    under the first category object's "Events" field.

    Args:
        get_group_data: Parsed JSON response from /GetGroup.

    Returns:
        A list of event IDs. Returns an empty list if no categories or no events
        are present in the response.

    Raises:
        TypeError: If the expected response structure is invalid.
    """
    categories = get_group_data.get("Categories", [])

    if not categories:
        return []

    if not isinstance(categories, list):
        raise TypeError("'Categories' is not a list")

    first_category = categories[0]

    if not isinstance(first_category, dict):
        raise TypeError("First item in 'Categories' is not a dictionary")

    events = first_category.get("Events", [])

    if not events:
        return []

    if not isinstance(events, list):
        raise TypeError("'Events' is not a list")

    return events


def extract_player_prop_markets(event_details: dict) -> list[str]:
    """
    Extract a limited set of player prop market identifiers from /GetEventDetails.

    This function scans the event's market list and selects:
    - up to 4 player total-points markets
    - up to 3 player total-rebounds markets

    The resulting list is later used to build the final payload for the
    /GetEventsWithMultipleMarkets endpoint.

    Args:
        event_details: Parsed JSON response from /GetEventDetails.

    Returns:
        A list of player prop MarketCName strings. Returns an empty list if no
        market data is present.

    Raises:
        TypeError: If the "Markets" field is not in the expected format.
    """
    markets = event_details.get("Markets", [])

    if not markets:
        return []

    if not isinstance(markets, list):
        raise TypeError("'Markets' is not a list")

    total_points_markets = []
    total_rebounds_markets = []

    for market in markets:
        if not isinstance(market, dict):
            continue

        market_cname = market.get("MarketCName")
        if not isinstance(market_cname, str):
            continue

        if (
            market_cname.startswith("-total-points-----")
            and len(total_points_markets) < 4
        ):
            total_points_markets.append(market_cname)

        elif (
            market_cname.startswith("-total-rebounds-----")
            and len(total_rebounds_markets) < 3
        ):
            total_rebounds_markets.append(market_cname)

        # Stop early once the target number of player prop markets has been collected
        if len(total_points_markets) == 4 and len(total_rebounds_markets) == 3:
            break

    return total_points_markets + total_rebounds_markets


def build_event_config(event_id: int, player_prop_markets: list[str]) -> dict | None:
    """
    Build an event configuration object for the /GetEventsWithMultipleMarkets endpoint.

    The configuration contains:
    - the event ID
    - the referer URL for the events web page
    - three default markets (money line, point spread, total points)
    - seven event-specific player prop markets

    Args:
        event_id: The Betway event ID.
        player_prop_markets: A list of extracted event-specific player prop MarketCName values.

    Returns:
        A dictionary containing the event configuration, or None if fewer than
        seven event-specific player prop markets are available.
    """
    if len(player_prop_markets) < 7:
        return None

    return {
        "event_id": event_id,
        "referer": f"https://betway.com/gb/en/sports/event/{event_id}",
        "market_cnames": [
            "money-line",
            "-point-spread---0",
            "-total-points---0",
            *player_prop_markets[:7],
        ],
    }


def build_event_configs_from_ids(event_ids: list[int], target_count: int = 5) -> list[dict]:
    """
    Build valid event configuration objects from a list of event IDs.

    For each event ID, the function:
    1. Fetches event details from /GetEventDetails
    2. Extracts player prop market identifiers
    3. Attempts to build a valid event configuration

    Invalid or incomplete events are skipped. For some events Betway may not post
    player prop markets at times. Processing stops early once the
    desired number of valid event configurations has been collected.

    Args:
        event_ids: A list of candidate Betway event IDs.
        target_count: The maximum number of valid event configurations to build.

    Returns:
        A list of valid event configuration dictionaries.
    """
    event_configs = []

    for event_id in event_ids:
        try:
            print(f"Processing event {event_id}...")

            event_details = fetch_get_event_details(event_id)
            player_prop_markets = extract_player_prop_markets(event_details)
            event_config = build_event_config(event_id, player_prop_markets)

            if event_config is None:
                print(f"Skipping event {event_id}: insufficient player prop markets")
                continue

            event_configs.append(event_config)
            print(f"Event {event_id} complete")

            if len(event_configs) == target_count:
                break

        except Exception as e:
            print(f"Failed processing event {event_id}: {e}")

    return event_configs


def build_get_events_with_multiple_markets_payload(event_config: dict) -> dict:
    """
    Build the JSON payload for the /GetEventsWithMultipleMarkets endpoint.

    This payload combines:
    - an event ID
    - a list of market identifiers (MarketCNames) for the event

    The event configuration is generated earlier in the workflow and defines
    which markets should be requested for a given event.

    Args:
        event_config: A dictionary containing:
            - event_id: The Betway event ID
            - market_cnames: List of market identifiers

    Returns:
        A dictionary representing the POST request payload for
        /GetEventsWithMultipleMarkets.
    """
    payload = dict(GET_EVENTS_WITH_MULTIPLE_MARKETS_DEFAULTS)
    payload["CorrelationId"] = str(uuid.uuid4())

    payload["EventMarketSets"] = [
        {
            "EventIds": [event_config["event_id"]],
            "MarketCNames": event_config["market_cnames"],
        }
    ]

    return payload


def fetch_get_events_with_multiple_markets(event_config: dict) -> dict:
    """
    Fetch market and odds data from the /GetEventsWithMultipleMarkets endpoint.

    This function uses the prepared event configuration to request multiple
    markets odds data for a single event in one API call.

    Args:
        event_config: A dictionary containing event ID, referer, and market list.

    Returns:
        The parsed JSON response from /GetEventsWithMultipleMarkets.
    """
    payload = build_get_events_with_multiple_markets_payload(event_config)
    headers = build_headers(BASE_HEADERS, referer=event_config["referer"])
    return post_json(GET_EVENTS_WITH_MULTIPLE_MARKETS_URL, headers, payload)


def parse_match(response_data: dict) -> Match:
    """
    Parse match-level data from a /GetEventsWithMultipleMarkets response.

    This function extracts high-level event details such as:
    - event ID
    - team names
    - start time
    - sport and league

    The function applies:
    - strict validation for structural fields (raises exceptions)
    - soft validation for optional fields (logs warnings and assigns defaults)

    Args:
        response_data: Parsed JSON response from
            /GetEventsWithMultipleMarkets.

    Returns:
        A Match object with basic event information populated.
        The odds list is initialized as empty and filled later.

    Raises:
        TypeError: If required structural fields are missing or invalid.
        ValueError: If no events are found in the response.
    """
    events = response_data.get("Events", [])

    if not isinstance(events, list):
        raise TypeError("'Events' is not a list")

    if not events:
        raise ValueError("No events found in response")

    first_event = events[0]

    if not isinstance(first_event, dict):
        raise TypeError("First item in 'Events' is not a dictionary")

    event_id = first_event.get("Id")
    if not isinstance(event_id, int):
        raise TypeError("'Id' is missing or is not an integer")

    home_team = first_event.get("HomeTeamName")
    if not isinstance(home_team, str) or not home_team:
        print("Warning: HomeTeamName is missing or invalid")
        home_team = ""

    away_team = first_event.get("AwayTeamName")
    if not isinstance(away_team, str) or not away_team:
        print("Warning: AwayTeamName is missing or invalid")
        away_team = ""

    date_str = first_event.get("Date")
    if not isinstance(date_str, str) or not date_str:
        print("Warning: Date is missing or invalid")
        date_str = ""

    time_str = first_event.get("Time")
    if not isinstance(time_str, str) or not time_str:
        print("Warning: Time is missing or invalid")
        time_str = ""

    sport = first_event.get("CategoryName")
    if not isinstance(sport, str) or not sport:
        print("Warning: CategoryName is missing or invalid")
        sport = ""

    league = first_event.get("GroupName")
    if not isinstance(league, str) or not league:
        print("Warning: GroupName is missing or invalid")
        league = ""

    try:
        start_time = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%Y %H:%M")
    except ValueError:
        print("Warning: Could not parse start_time")
        start_time = None

    return Match(
        id=str(event_id),
        home_team=home_team,
        away_team=away_team,
        start_time=start_time,
        sport=sport,
        league=league,
        odds=[],
    )


def parse_odds(response_data: dict) -> list[Odd]:
    """
    Parse live betting odds-level data from a /GetEventsWithMultipleMarkets response.

    This function:
    1. Builds a lookup dictionary mapping MarketIds to human-readable betting market titles
    2. Iterates through all objects, validating required fields
    3. Converts decimal odds to American format
    4. Constructs Odd dataclass instances, using the lookup dictionary

    Invalid or incomplete outcomes are skipped rather than causing the function
    to fail. This ensures partial data can still be returned.

    Args:
        response_data: Parsed JSON response from
            /GetEventsWithMultipleMarkets.

    Returns:
        A list of Odd objects representing live valid betting markets and their odds.

    Raises:
        TypeError: If "Markets" or "Outcomes" are not lists.
        ValueError: If required top-level structures are empty.
    """
    markets = response_data.get("Markets", [])
    outcomes = response_data.get("Outcomes", [])

    if not isinstance(markets, list):
        raise TypeError("'Markets' is not a list")

    if not markets:
        raise ValueError("No markets found in response")

    if not isinstance(outcomes, list):
        raise TypeError("'Outcomes' is not a list")

    if not outcomes:
        raise ValueError("No outcomes found in response")

    market_lookup = {}

    for market in markets:
        if not isinstance(market, dict):
            continue

        market_id = market.get("Id")
        market_title = market.get("Title")

        # Build lookup dictionary mapping MarketId -> human-readable market title
        if isinstance(market_id, int) and isinstance(market_title, str) and market_title:
            market_lookup[market_id] = market_title

    parsed_odds = []

    for outcome in outcomes:
        if not isinstance(outcome, dict):
            continue

        outcome_id = outcome.get("Id")
        market_id = outcome.get("MarketId")
        bet_name = outcome.get("BetName")
        odds_decimal = outcome.get("OddsDecimal")

        # Skip invalid or incomplete outcome values
        if not isinstance(outcome_id, int):
            continue

        if not isinstance(market_id, int):
            continue

        if not isinstance(bet_name, str) or not bet_name:
            continue

        if not isinstance(odds_decimal, (int, float)):
            continue

        market_name = market_lookup.get(market_id)
        if not isinstance(market_name, str) or not market_name:
            continue

        try:
            american_odds = decimal_to_american(float(odds_decimal))
        except ValueError:
            continue

        parsed_odds.append(
            Odd(
                id=str(outcome_id),
                market=market_name,
                bet_name=bet_name,
                american_odds=american_odds,
            )
        )

    return parsed_odds


def parse_get_events_with_multiple_markets_response(response_data: dict) -> Match:
    """
    Parse a complete match object from a /GetEventsWithMultipleMarkets response.

    This function combines:
    - match-level data parsing
    - odds-level data parsing
    into a single Match object.

    Args:
        response_data: Parsed JSON response from
            /GetEventsWithMultipleMarkets.

    Returns:
        A populated Match object containing both match
        attributes and a list of populated odds objects.

     Raises:
        ValueError: If no valid odds could be parsed from the response.
    """
    match = parse_match(response_data)
    match.odds = parse_odds(response_data)
    
    if not match.odds:
        raise ValueError("No valid odds could be parsed from response")

    return match


def save_raw_response_json(event_id: int, response_data: dict) -> None:
    """
    Save raw API response data to a JSON file for debugging and validation.

    File output is controlled by the SAVE_RAW_RESPONSES configuration flag.
    If disabled, the function exits without performing any file operations.

    The file is saved to:
        output/event_<event_id>_raw.json

    Existing files are overwritten to maintain only the latest snapshot.

    Args:
        event_id: The Betway event ID associated with the response.
        response_data: The raw JSON response data to save.
    """
    if not SAVE_RAW_RESPONSES:
        return

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"event_{event_id}_raw.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(response_data, file, indent=2)


def fetch_and_parse_matches(event_configs: list[dict]) -> tuple[list[Match], int]:
    """
    Fetch and parse Match class data for a list of event configurations.

    For each event configuration, this function:
    1. Calls /GetEventsWithMultipleMarkets
    2. Optionally saves the raw response
    3. Parses the response into a Match object
    4. Tracks any failures

    A small delay is introduced between requests to reduce request burst rate.

    Args:
        event_configs: A list of event configuration dictionaries.

    Returns:
        A tuple containing:
            - A list of successfully parsed Match objects
            - An integer count of failed event processing attempts
    """
    matches = []
    failure_count = 0

    for event_config in event_configs:
        event_id = event_config["event_id"]
        print(f"Processing event {event_id}...")

        try:
            response_data = fetch_get_events_with_multiple_markets(event_config)
            save_raw_response_json(event_id, response_data)
            match = parse_get_events_with_multiple_markets_response(response_data)
            matches.append(match)
            print(f"Event {event_id} parsed successfully")

        except Exception as e:
            failure_count += 1
            print(f"Failed processing event {event_id}: {e}")

        # Introduce a small delay to avoid rapid consecutive requests
        time.sleep(1)

    return matches, failure_count


def main():
    """
    Main execution workflow for the Betway NBA odds scraper.

    This function orchestrates the entire data pipeline:

    Step 1:
        Fetch event group data from /GetGroup to discover available events.

    Step 2:
        Extract event IDs from the group response.

    Step 3:
        Build event configurations by:
        - fetching event details from /GetEventDetails
        - extracting player prop markets
        - constructing payload-ready configurations

    Step 4:
        Continuously poll /GetEventsWithMultipleMarkets to:
        - retrieve odds data
        - parse responses into Match and Odd objects
        - display structured results

    The polling loop includes:
        - rate limiting (fixed interval between cycles)
        - per-request delay to reduce burst traffic
        - failure tracking per cycle
        - cooldown logic when failure threshold is exceeded

    Error Handling:
        - Gracefully exits on user interruption (Ctrl+C)
        - Catches unexpected errors and logs them without crashing abruptly
    """
    try:
        #Step 1: Fetch initial event group data
        print("Step 1: Fetching /GetGroup data...")
        get_group_data = fetch_get_group_data()
        print("Step 1 complete")

        #Step 2: Extract event ids
        print("Step 2: Extracting event ids...")
        event_ids = extract_event_ids(get_group_data)

        if not event_ids:
            print("No event IDs found in /GetGroup data.")
            return

        print("Step 2 complete:", event_ids)

        #Step 3: Build event configurations
        print("Step 3: Building event configs from /GetEventDetails...")
        event_configs = build_event_configs_from_ids(event_ids, target_count=5)

        if not event_configs:
            print("Workflow aborted: unable to build any valid event configs.")
            return

        if len(event_configs) < 5:
            print(f"Only {len(event_configs)} valid event configs were available.")
            print("Proceeding with available event configs.")
        else:
            print("Successfully built 5 valid event configs.")

        print("Step 3 complete, final event configs:")
        for event_config in event_configs:
            print(event_config)

        #Step 4: Continuous polling for odds updates
        print("Step 4: Starting continuous polling for /GetEventsWithMultipleMarkets...")

        poll_interval_seconds = 90
        cooldown_seconds = 600
        failure_threshold = 5

        while True:
            print("\nStarting new polling cycle...")
            matches, failure_count = fetch_and_parse_matches(event_configs)

            print(f"Polling cycle complete. Parsed {len(matches)} match(es).")
            print(f"Polling cycle failures: {failure_count}")

            # Handle case where no matches were successfully parsed
            if not matches:
                print("No valid matches were parsed in this cycle.")
            else:
                print("\nFinal Parsed Matches:\n")

                for match in matches:
                    print(f"Match ID: {match.id}")
                    print(f"{match.home_team} vs {match.away_team}")
                    print(f"League: {match.league} | Sport: {match.sport}")
                    print(f"Start Time: {match.start_time}")
                    print("Odds:")

                    for odd in match.odds:
                        print(f"  [{odd.market}] {odd.bet_name}: {odd.american_odds}")

                    print("-" * 50)

            # Apply cooldown if too many failures occurred
            if failure_count >= failure_threshold:
                print(f"Failure threshold reached. Cooling down for {cooldown_seconds} seconds...")
                time.sleep(cooldown_seconds)

            else:
                print(f"Sleeping for {poll_interval_seconds} seconds before next refresh...")
                time.sleep(poll_interval_seconds)

    except KeyboardInterrupt:
        # Graceful shutdown on user interruption
        print("\nPolling stopped by user.")

    except Exception as e:
        # Catch-all for important errors in the workflow
        print("Workflow failed:", e)


if __name__ == "__main__":
    main()




