"""
Tests for the GeoService.
"""

import pytest
import httpx
from unittest.mock import MagicMock, AsyncMock
from countryinfo import CountryInfo # Import CountryInfo to mock it

from fastapi import HTTPException
from src.efficient_tutor_backend.services.geo_service import GeoService

@pytest.mark.anyio
class TestGeoService:
    """Test suite for the GeoService."""

    @pytest.fixture
    def geo_service(self) -> GeoService:
        """Provides a GeoService instance for testing."""
        return GeoService()

    async def test_get_location_info_success_us(self, geo_service: GeoService, mocker):
        """
        Tests a successful geolocation lookup for a US IP address.
        """
        print("\n--- Testing GeoService successful lookup (US) ---")
        
        # 1. ARRANGE: Mock the httpx response
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={
            "status": "success",
            "countryCode": "US",
            "timezone": "America/New_York"
        })
        mock_response.raise_for_status = MagicMock()

        # Patch httpx.AsyncClient.get directly
        mocker.patch('httpx.AsyncClient.get', new_callable=AsyncMock, return_value=mock_response)

        # Mock CountryInfo
        mock_country_info_instance = MagicMock()
        mock_country_info_instance.currencies.return_value = ["USD"]
        mocker.patch('src.efficient_tutor_backend.services.geo_service.CountryInfo', return_value=mock_country_info_instance)

        # 2. ACT
        ip_address = "8.8.8.8" # A public Google DNS IP
        location_info = await geo_service.get_location_info(ip_address)

        # 3. ASSERT
        assert location_info is not None
        assert location_info["timezone"] == "America/New_York"
        assert location_info["currency"] == "USD"
        
        # Verify that the mock was called correctly
        httpx.AsyncClient.get.assert_called_once_with(f"http://ip-api.com/json/{ip_address}")
        mock_country_info_instance.currencies.assert_called_once()
        print(f"--- Successfully verified location: {location_info} ---")

    async def test_get_location_info_success_uk(self, geo_service: GeoService, mocker):
        """
        Tests a successful geolocation lookup for a UK IP address.
        """
        print("\n--- Testing GeoService successful lookup (UK) ---")
        
        # 1. ARRANGE
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={
            "status": "success",
            "countryCode": "GB",
            "timezone": "Europe/London"
        })
        mock_response.raise_for_status = MagicMock()

        mocker.patch('httpx.AsyncClient.get', new_callable=AsyncMock, return_value=mock_response)

        mock_country_info_instance = MagicMock()
        mock_country_info_instance.currencies.return_value = ["GBP"]
        mocker.patch('src.efficient_tutor_backend.services.geo_service.CountryInfo', return_value=mock_country_info_instance)

        # 2. ACT
        ip_address = "212.58.244.23" # A public BBC IP
        location_info = await geo_service.get_location_info(ip_address)

        # 3. ASSERT
        assert location_info is not None
        assert location_info["timezone"] == "Europe/London"
        assert location_info["currency"] == "GBP"
        print(f"--- Successfully verified location: {location_info} ---")

    async def test_get_location_info_api_failure(self, geo_service: GeoService, mocker):
        """
        Tests handling of an API failure response (e.g., for a private IP).
        """
        print("\n--- Testing GeoService API failure response ---")
        
        # 1. ARRANGE
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={
            "status": "fail",
            "message": "private range"
        })
        mock_response.raise_for_status = MagicMock()

        mocker.patch('httpx.AsyncClient.get', new_callable=AsyncMock, return_value=mock_response)

        # Mock CountryInfo (it shouldn't be called in this path, but good to have a mock)
        mock_country_info_instance = MagicMock()
        mocker.patch('src.efficient_tutor_backend.services.geo_service.CountryInfo', return_value=mock_country_info_instance)

        # 2. ACT & ASSERT
        ip_address = "192.168.1.1"
        with pytest.raises(HTTPException) as exc_info:
            await geo_service.get_location_info(ip_address)

        assert exc_info.value.status_code == 400
        assert "private range" in exc_info.value.detail
        mock_country_info_instance.currencies.assert_not_called()
        print(f"--- Correctly raised HTTPException {exc_info.value.status_code} ---")

    async def test_get_location_info_incomplete_data(self, geo_service: GeoService, mocker):
        """
        Tests handling of an incomplete but successful API response.
        """
        print("\n--- Testing GeoService incomplete data response ---")
        
        # 1. ARRANGE
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={
            "status": "success",
            "countryCode": "US"
            # No timezone
        })
        mock_response.raise_for_status = MagicMock()

        mocker.patch('httpx.AsyncClient.get', new_callable=AsyncMock, return_value=mock_response)

        # Mock CountryInfo (it shouldn't be called in this path, but good to have a mock)
        mock_country_info_instance = MagicMock()
        mocker.patch('src.efficient_tutor_backend.services.geo_service.CountryInfo', return_value=mock_country_info_instance)

        # 2. ACT & ASSERT
        ip_address = "8.8.8.8"
        with pytest.raises(HTTPException) as exc_info:
            await geo_service.get_location_info(ip_address)

        assert exc_info.value.status_code == 400
        assert "Could not determine timezone or country" in exc_info.value.detail
        mock_country_info_instance.currencies.assert_not_called()
        print(f"--- Correctly raised HTTPException {exc_info.value.status_code} ---")

    async def test_get_location_info_no_currency_found(self, geo_service: GeoService, mocker):
        """
        Tests the default currency behavior when a country has no currency (e.g., Antarctica).
        """
        print("\n--- Testing GeoService default currency fallback ---")
        
        # 1. ARRANGE
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={
            "status": "success",
            "countryCode": "AQ", # Antarctica
            "timezone": "Antarctica/McMurdo"
        })
        mock_response.raise_for_status = MagicMock()

        mocker.patch('httpx.AsyncClient.get', new_callable=AsyncMock, return_value=mock_response)

        # Mock CountryInfo to return an empty list for currencies
        mock_country_info_instance = MagicMock()
        mock_country_info_instance.currencies.return_value = []
        mocker.patch('src.efficient_tutor_backend.services.geo_service.CountryInfo', return_value=mock_country_info_instance)

        # 2. ACT
        ip_address = "1.2.3.4" # Dummy IP
        location_info = await geo_service.get_location_info(ip_address)

        # 3. ASSERT
        assert location_info is not None
        assert location_info["timezone"] == "Antarctica/McMurdo"
        assert location_info["currency"] == "USD" # Should default to USD
        mock_country_info_instance.currencies.assert_called_once()
        print(f"--- Successfully verified currency fallback: {location_info} ---")

    async def test_get_location_info_http_request_error(self, geo_service: GeoService, mocker):
        """
        Tests handling of an httpx.RequestError during the API call.
        """
        print("\n--- Testing GeoService httpx.RequestError handling ---")
        
        # 1. ARRANGE
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={}) # Not used in this path, but good to have
        mock_response.raise_for_status.side_effect = httpx.RequestError("Network error")

        mocker.patch('httpx.AsyncClient.get', new_callable=AsyncMock, return_value=mock_response)

        # Mock CountryInfo (it shouldn't be called in this path)
        mock_country_info_instance = MagicMock()
        mocker.patch('src.efficient_tutor_backend.services.geo_service.CountryInfo', return_value=mock_country_info_instance)

        # 2. ACT & ASSERT
        ip_address = "8.8.8.8"
        with pytest.raises(HTTPException) as exc_info:
            await geo_service.get_location_info(ip_address)

        assert exc_info.value.status_code == 503
        assert "Geolocation service is currently unavailable" in exc_info.value.detail
        mock_country_info_instance.currencies.assert_not_called()
        print(f"--- Correctly raised HTTPException {exc_info.value.status_code} ---")

    async def test_get_location_info_http_status_error(self, geo_service: GeoService, mocker):
        """
        Tests handling of an httpx.HTTPStatusError (e.g., 500 from the API).
        """
        print("\n--- Testing GeoService httpx.HTTPStatusError handling ---")
        
        # 1. ARRANGE
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={}) # Not used in this path, but good to have
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500, text="Internal Server Error")
        )

        mocker.patch('httpx.AsyncClient.get', new_callable=AsyncMock, return_value=mock_response)

        # Mock CountryInfo (it shouldn't be called in this path)
        mock_country_info_instance = MagicMock()
        mocker.patch('src.efficient_tutor_backend.services.geo_service.CountryInfo', return_value=mock_country_info_instance)

        # 2. ACT & ASSERT
        ip_address = "8.8.8.8"
        with pytest.raises(HTTPException) as exc_info:
            await geo_service.get_location_info(ip_address)

        assert exc_info.value.status_code == 500
        assert "Geolocation service error: Internal Server Error" in exc_info.value.detail
        mock_country_info_instance.currencies.assert_not_called()
        print(f"--- Correctly raised HTTPException {exc_info.value.status_code} ---")
