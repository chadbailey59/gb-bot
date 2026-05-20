"""Gradient Bang API client.

Handles login, character lookup/creation, and starting a game session that
returns Daily room credentials. Shared by the voice bots in this repo.
"""

from __future__ import annotations

import os

import aiohttp
from loguru import logger

GB_ENV = os.environ.get("GB_ENV", "prod").strip().lower()
API_BASES = {
    "prod": os.environ.get("GB_API_BASE_PROD", "https://api.gradient-bang.com/functions/v1"),
    "local": os.environ.get("GB_API_BASE_LOCAL", "http://127.0.0.1:54321/functions/v1"),
}
API_BASE = API_BASES.get(GB_ENV, API_BASES["prod"]).rstrip("/")
EMAIL = os.environ.get("GB_EMAIL")
PASSWORD = os.environ.get("GB_PASSWORD")
CHARACTER_NAME = os.environ.get("GB_CHARACTER", "HyperionBot")


async def api_login(session: aiohttp.ClientSession) -> dict:
    if not EMAIL or not PASSWORD:
        raise RuntimeError("GB_EMAIL and GB_PASSWORD are required unless --room-url is provided")

    async with session.post(
        f"{API_BASE}/login",
        json={"email": EMAIL, "password": PASSWORD},
    ) as response:
        response.raise_for_status()
        return await response.json()


async def api_create_character(
    session: aiohttp.ClientSession,
    token: str,
    name: str,
) -> dict:
    async with session.post(
        f"{API_BASE}/user_character_create",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    ) as response:
        response.raise_for_status()
        return await response.json()


async def api_start_bot(
    session: aiohttp.ClientSession,
    token: str,
    character_id: str,
) -> dict:
    async with session.post(
        f"{API_BASE}/start",
        json={
            "createDailyRoom": True,
            "dailyRoomProperties": {
                "start_video_off": True,
                "eject_at_room_exp": True,
            },
            "body": {
                "character_id": character_id,
                "bypass_tutorial": True,
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    ) as response:
        response.raise_for_status()
        return await response.json()


async def login_and_start() -> tuple[str, str]:
    """Login, select/create character, start a session, return (room_url, room_token)."""
    logger.info(f"[1] Logging in ({GB_ENV}, {API_BASE})...")
    async with aiohttp.ClientSession() as session:
        login_data = await api_login(session)
        token = login_data["session"]["access_token"]
        characters = login_data.get("characters", [])
        logger.info(f"    Logged in as {login_data['user']['email']}")

        character_id = None
        for character in characters:
            if character["name"] == CHARACTER_NAME:
                character_id = character["character_id"]
                logger.info(f"    Using character: {CHARACTER_NAME} ({character_id})")
                break

        if not character_id:
            logger.info(f"    Creating character: {CHARACTER_NAME}...")
            result = await api_create_character(session, token, CHARACTER_NAME)
            character_id = result["character_id"]
            logger.info(f"    Created: {character_id}")

        logger.info("[2] Starting game session...")
        start_data = await api_start_bot(session, token, character_id)
        room_url = start_data["dailyRoom"]
        room_token = start_data["dailyToken"]
        session_id = start_data.get("sessionId", "?")
        logger.info(f"    Room: {room_url}")
        logger.info(f"    Join: {room_url}?t={room_token}")
        logger.info(f"    Session: {session_id}")
        return room_url, room_token
