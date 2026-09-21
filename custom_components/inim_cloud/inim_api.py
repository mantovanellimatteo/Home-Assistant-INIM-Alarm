"""Asynchronous API client for Inim Cloud REST and WebSocket services."""
import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional
import urllib.parse

import aiohttp

from .const import (
    API_BASE_URL,
    DEFAULT_CLIENT_APP,
    DEFAULT_CLIENT_INFO,
    DEFAULT_CLIENT_PLATFORM,
    DEFAULT_CLIENT_VERSION,
    WSS_BASE_URL,
)
from .security import redact_sensitive_data

_LOGGER = logging.getLogger(__name__)


class InimApiError(Exception):
    """General Inim Cloud API error."""


class InimAuthError(InimApiError):
    """Authentication or credential error."""


class InimConnectionError(InimApiError):
    """Connection or network error."""


class InimApiClient:
    """Encapsulates authenticated REST calls and real-time WebSocket listening."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        client_id: str,
        client_name: str,
    ) -> None:
        self.session = session
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client_name = client_name
        self.token: Optional[str] = None
        self._lock = asyncio.Lock()

    async def async_login(self) -> str:
        """Authenticate with Inim Cloud via RegisterClient and obtain a session token."""
        async with self._lock:
            payload = {
                "Node": "",
                "Name": "",
                "ClientIP": "",
                "Method": "RegisterClient",
                "Token": "",
                "ClientId": self.client_id,
                "Params": {
                    "Username": self.username,
                    "Password": self.password,
                    "ClientId": self.client_id,
                    "ClientName": self.client_name,
                    "ClientInfo": DEFAULT_CLIENT_INFO,
                    "ClientApp": DEFAULT_CLIENT_APP,
                    "ClientVersion": DEFAULT_CLIENT_VERSION,
                    "ClientPlatform": DEFAULT_CLIENT_PLATFORM,
                },
            }

            try:
                json_str = json.dumps(payload, separators=(",", ":"))
                form_data = urllib.parse.urlencode({"req": json_str})

                _LOGGER.debug(
                    "Sending RegisterClient to Inim Cloud: %s",
                    redact_sensitive_data(payload),
                )

                async with self.session.post(
                    API_BASE_URL,
                    data=form_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status != 200:
                        raise InimConnectionError(
                            f"HTTP server error during login: {resp.status}"
                        )
                    body = await resp.text()
                    res = json.loads(body)

                status = res.get("Status")
                if status == 0 and "Data" in res and "Token" in res["Data"]:
                    self.token = res["Data"]["Token"]
                    _LOGGER.info("Inim Cloud authentication successful. Obtained session token.")
                    return self.token

                # Check for auth failure
                err_msg = res.get("ErrMsg", "Unknown error")
                if status in (4, 7) or "Invalid username or password" in err_msg:
                    raise InimAuthError(f"Invalid credentials: {err_msg}")
                raise InimApiError(f"RegisterClient failed [status {status}]: {err_msg}")

            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                raise InimConnectionError(f"Failed to connect to Inim Cloud: {err}") from err

    async def async_get_devices(self) -> Dict[str, Any]:
        """Fetch full device topology, scenarios, and zones from Inim Cloud."""
        return await self._async_call_api("GetDevicesExtended", {})

    async def async_activate_scenario(self, device_id: int, scenario_id: int) -> bool:
        """Send scenario activation command to Inim Cloud."""
        params = {
            "DeviceId": device_id,
            "ScenarioId": scenario_id,
            "ClientId": self.client_id,
        }
        res = await self._async_call_api("ActivateScenario", params)
        return res.get("Status") == 0

    async def _async_call_api(
        self,
        method: str,
        params: Dict[str, Any],
        retry_on_auth: bool = True,
        retry_on_rate_limit: bool = True,
    ) -> Dict[str, Any]:
        """Execute an authenticated Inim Cloud API request."""
        if not self.token:
            await self.async_login()

        payload = {
            "Node": "",
            "Name": "",
            "ClientIP": "",
            "Method": method,
            "Token": self.token,
            "ClientId": self.client_id,
            "Params": params,
        }

        try:
            json_str = json.dumps(payload, separators=(",", ":"))
            form_data = urllib.parse.urlencode({"req": json_str})

            async with self.session.post(
                API_BASE_URL,
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                body = await resp.text()
                try:
                    res = json.loads(body)
                except json.JSONDecodeError:
                    res = {}

                if resp.status != 200:
                    if retry_on_auth and self._is_expired_token_response(res):
                        _LOGGER.warning("Inim session token expired, re-authenticating...")
                        await self.async_login()
                        return await self._async_call_api(
                            method,
                            params,
                            retry_on_auth=False,
                            retry_on_rate_limit=retry_on_rate_limit,
                        )

                    if resp.status == 429 and retry_on_rate_limit:
                        retry_after = resp.headers.get("Retry-After")
                        try:
                            delay = min(max(float(retry_after), 1), 30)
                        except (TypeError, ValueError):
                            delay = 5
                        _LOGGER.warning(
                            "Inim Cloud rate limit during %s, retrying in %.0fs",
                            method,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        return await self._async_call_api(
                            method,
                            params,
                            retry_on_auth=retry_on_auth,
                            retry_on_rate_limit=False,
                        )

                    raise InimConnectionError(f"HTTP error during {method}: {resp.status}")

            status = res.get("Status")
            # If session token expired or invalid (e.g. status 1 or status 3)
            if self._is_expired_token_response(res) and retry_on_auth:
                _LOGGER.warning("Inim session token expired, re-authenticating...")
                await self.async_login()
                return await self._async_call_api(
                    method,
                    params,
                    retry_on_auth=False,
                    retry_on_rate_limit=retry_on_rate_limit,
                )

            if status != 0:
                raise InimApiError(f"{method} returned error [status {status}]: {res.get('ErrMsg')}")

            return res

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise InimConnectionError(f"Connection failed during {method}: {err}") from err

    @staticmethod
    def _is_expired_token_response(response: Dict[str, Any]) -> bool:
        """Return whether an API response indicates an expired session token."""
        status = response.get("Status")
        message = str(response.get("ErrMsg", "")).lower()
        return status in (1, 3, 6, 27) or (
            "token" in message and ("expired" in message or "invalid" in message)
        )

    async def async_listen_events(
        self,
        on_event_callback: Callable[[Dict[str, Any]], Any],
        is_running_check: Callable[[], bool],
    ) -> None:
        """Maintain persistent WebSocket connection with automatic reconnect and keep-alives."""
        backoff = 5
        while is_running_check():
            try:
                if not self.token:
                    await self.async_login()

                payload = {
                    "Node": "",
                    "Name": "",
                    "ClientIP": "",
                    "Method": "WebSocketStart",
                    "Token": self.token,
                    "ClientId": self.client_id,
                    "Params": {
                        "Username": self.username,
                        "Password": self.password,
                        "ClientId": self.client_id,
                        "ClientName": self.client_name,
                        "ClientInfo": DEFAULT_CLIENT_INFO,
                        "ClientApp": DEFAULT_CLIENT_APP,
                        "ClientVersion": DEFAULT_CLIENT_VERSION,
                        "ClientPlatform": DEFAULT_CLIENT_PLATFORM,
                    },
                }

                json_str = json.dumps(payload, separators=(",", ":"))
                escaped_req = urllib.parse.quote(json_str)
                wss_url = f"{WSS_BASE_URL}?req={escaped_req}"

                _LOGGER.debug("Connecting to Inim Cloud WebSocket...")
                # Use aiohttp client WebSocket with built-in heartbeat ping/pong
                async with self.session.ws_connect(
                    wss_url,
                    heartbeat=30.0,
                    timeout=aiohttp.ClientWSTimeout(ws_close=10.0),
                ) as ws:
                    _LOGGER.info("Inim Cloud WebSocket connected. Receiving push events.")
                    backoff = 5  # Reset backoff on successful connection

                    async for msg in ws:
                        if not is_running_check():
                            break

                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                _LOGGER.debug("Inim WebSocket event received: %s", data)
                                if asyncio.iscoroutinefunction(on_event_callback):
                                    await on_event_callback(data)
                                else:
                                    on_event_callback(data)
                            except Exception as parse_err:
                                _LOGGER.warning("Error processing WebSocket payload: %s", parse_err)

                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            _LOGGER.warning("Inim WebSocket connection closed/error: %s", msg)
                            break

            except asyncio.CancelledError:
                _LOGGER.debug("WebSocket listener cancelled.")
                break
            except Exception as err:
                _LOGGER.warning(
                    "Inim WebSocket connection lost (%s). Reconnecting in %ds...",
                    err,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
                # Invalidate token to refresh on next attempt
                self.token = None
