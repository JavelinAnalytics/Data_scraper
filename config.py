SAVE_RAW_RESPONSES = True

GET_GROUP_URL = "https://betway.com/gb/services/api/events/v2/GetGroup"

GET_EVENT_DETAILS_URL = "https://betway.com/gb/services/api/events/v2/GetEventDetails"

GET_EVENTS_WITH_MULTIPLE_MARKETS_URL = (
    "https://betway.com/gb/services/api/events/v2/GetEventsWithMultipleMarkets"
)

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://betway.com",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}

GET_GROUP_DEFAULTS = {
    "BrandId": 3,
    "LanguageId": 1,
    "TerritoryId": 227,
    "TerritoryCode": "GB",
    "ClientTypeId": 2,
    "JurisdictionId": 1,
    "ClientIntegratorId": 1,
    "GroupCName": "nba",
    "CategoryCName": "basketball",
    "SubCategoryCName": "usa",
    "PremiumOnly": False,
}

GET_EVENT_DETAILS_DEFAULTS = {
    "BrandId": 3,
    "LanguageId": 1,
    "TerritoryId": 227,
    "TerritoryCode": "GB",
    "ClientTypeId": 2,
    "JurisdictionId": 1,
    "ClientIntegratorId": 1,
    "ScoreboardRequest": {
        "IncidentRequest": {},
        "ScoreboardType": 3,
    },
}

GET_EVENTS_WITH_MULTIPLE_MARKETS_DEFAULTS = {
    "BrandId": 3,
    "LanguageId": 1,
    "TerritoryId": 227,
    "TerritoryCode": "GB",
    "ClientTypeId": 1,
    "JurisdictionId": 1,
    "ClientIntegratorId": 1,
    "ScoreboardRequest": {
        "IncidentRequest": {},
        "ScoreboardType": 3,
    },
}

REQUEST_TIMEOUT_SECONDS = 20