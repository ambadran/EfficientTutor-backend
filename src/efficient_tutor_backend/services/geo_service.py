import httpx # Using httpx for async requests
from countryinfo import CountryInfo
from fastapi import HTTPException, status
from ..common.logger import log
import asyncio
import inspect

class GeoService:
    """
    Service to handle geolocation lookups based on IP address.
    Uses ip-api.com for IP to location data and countryinfo for currency.
    """
    IP_API_URL = "http://ip-api.com/json/"

    async def get_location_info(self, ip_address: str) -> dict:
        """
        Fetches geolocation information (timezone, country code, currency) for a given IP address.
        """
        log.info(f"Fetching geolocation for IP: {ip_address}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.IP_API_URL}{ip_address}")
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                data = response.json()

            if data.get("status") == "fail":
                message = data.get('message', 'Unknown error')
                if "reserved range" in message.lower():
                    log.warning(f"Geolocation lookup failed for IP {ip_address} due to 'Reserved Range'.")
                    timezone = None 
                    country_code = None
                    currency = None
                else:
                    log.warning(f"Geolocation lookup failed for IP {ip_address}: {message}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Could not determine location for IP address: {ip_address}. Reason: {message}"
                    )

            timezone = data.get("timezone")
            country_code = data.get("countryCode")

            # Defensive check for mocking in tests
            if inspect.isawaitable(country_code):
                country_code = await country_code
            if inspect.isawaitable(timezone):
                timezone = await timezone


            if not timezone or not country_code:
                log.warning(f"Incomplete geolocation data for IP {ip_address}: {data}. Using default timezone 'UTC' and currency 'USD'.")
                timezone = None
                country_code = None
                currency = None


            # Use countryinfo to get currency in a separate thread to avoid blocking
            def get_currency_sync(code: str) -> list:
                return CountryInfo(code).currencies()

            currencies = await asyncio.to_thread(get_currency_sync, country_code)
            
            if not currencies:
                log.warning(f"Could not determine currency for country code: {country_code}")
                currency = None
            else:
                currency = currencies[0] # Take the first currency if multiple are listed

            log.info(f"Geolocation successful for IP {ip_address}: Timezone={timezone}, Currency={currency}")
            return {"timezone": timezone, "currency": currency}

        except httpx.RequestError as e:
            log.error(f"HTTP request failed for geolocation service for IP {ip_address}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Geolocation service is currently unavailable. Please Try Again!"
            )
        except httpx.HTTPStatusError as e:
            log.error(f"Geolocation service returned an error for IP {ip_address}: {e.response.status_code} - {e.response.text}", exc_info=True)
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Geolocation service error: {e.response.text}"
            )
        except HTTPException:
            # Re-raise HTTPException to ensure it's not caught by the generic exception handler
            raise
        except Exception as e:
            log.error(f"An unexpected error occurred during geolocation for IP {ip_address}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during geolocation."
            )
