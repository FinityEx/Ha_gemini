"""Conversation platform for Gemini HA.

Implements a Home Assistant conversation agent backed by the Gemini Live API.
Supports natural language, multi-turn history, and HA entity tool calls.
"""
from __future__ import annotations

import logging
from typing import Literal

from homeassistant.components import conversation
from homeassistant.components.conversation import (
    ConversationInput,
    ConversationResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_API_KEY,
    CONF_CHAT_MODEL,
    DEFAULT_CHAT_MODEL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = (
    "You are a helpful Home Assistant voice assistant powered by Google Gemini. "
    "Help the user control smart home devices, answer questions about their home, "
    "and perform actions using the provided tools. "
    "Be concise, friendly, and confirm actions after you perform them."
)

# Maximum number of turns kept in per-entity conversation history.
_MAX_HISTORY_TURNS = 20


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Gemini conversation entity."""
    async_add_entities([GeminiConversationEntity(config_entry)])


class GeminiConversationEntity(
    conversation.ConversationEntity,
):
    """Gemini-powered conversation agent for Home Assistant.

    Uses the Gemini chat API with a persistent per-conversation history and an
    optional set of HA-entity tools so the model can control devices directly.
    """

    _attr_has_entity_name = True
    _attr_name = "Gemini Conversation"

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise the conversation entity."""
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_conversation"
        # conversation_id -> list of {"role": ..., "parts": [...]} dicts
        self._histories: dict[str, list[dict]] = {}

    @property
    def attribution(self) -> dict[str, str]:
        """Return attribution information."""
        return {"name": "Powered by Google Gemini", "url": "https://gemini.google.com"}

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """All languages are supported – Gemini handles multilingual input."""
        return "*"

    async def async_process(
        self, user_input: ConversationInput
    ) -> ConversationResult:
        """Process a user message and return the agent's response."""
        from google import genai  # noqa: PLC0415
        from google.genai import types  # noqa: PLC0415

        api_key: str = self._config_entry.data[CONF_API_KEY]
        model: str = self._config_entry.options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL)

        # Retrieve (or start) the history for this conversation.
        conv_id = user_input.conversation_id or user_input.device_id or "default"
        history = self._histories.setdefault(conv_id, [])

        # Append the new user turn.
        history.append(
            {
                "role": "user",
                "parts": [{"text": user_input.text}],
            }
        )

        # Trim history to avoid exceeding context limits.
        if len(history) > _MAX_HISTORY_TURNS * 2:
            history = history[-(  _MAX_HISTORY_TURNS * 2):]
            self._histories[conv_id] = history

        # Build the HA-entity tool definitions.
        ha_tools = _build_ha_tools(self.hass)

        client = genai.Client(api_key=api_key)

        try:
            contents = [
                types.Content(role=turn["role"], parts=[types.Part(text=p["text"]) for p in turn["parts"]])
                for turn in history
            ]

            generate_config = types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                tools=ha_tools if ha_tools else None,
            )

            response = await self.hass.async_add_executor_job(
                lambda: client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=generate_config,
                )
            )

            # Handle function/tool calls returned by the model.
            response_text, tool_results = await _handle_tool_calls(
                self.hass, response
            )

            # If there were tool calls, send the results back and get the final reply.
            if tool_results:
                history.append(
                    {"role": "model", "parts": [{"text": response_text or ""}]}
                )
                for tr in tool_results:
                    history.append({"role": "user", "parts": [{"text": tr}]})

                follow_up_contents = [
                    types.Content(
                        role=turn["role"],
                        parts=[types.Part(text=p["text"]) for p in turn["parts"]],
                    )
                    for turn in history
                ]

                def _follow_up(
                    _client=client,
                    _model=model,
                    _contents=follow_up_contents,
                    _config=generate_config,
                ):
                    return _client.models.generate_content(
                        model=_model,
                        contents=_contents,
                        config=_config,
                    )

                response = await self.hass.async_add_executor_job(_follow_up)
                response_text = (response.text or "").strip()

            if not response_text:
                response_text = "I'm sorry, I couldn't generate a response."

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Gemini conversation error: %s", err)
            response_text = "Sorry, I encountered an error processing your request."

        # Store the model's final reply in history.
        history.append(
            {"role": "model", "parts": [{"text": response_text}]}
        )

        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response_text)

        return ConversationResult(
            response=intent_response,
            conversation_id=conv_id,
        )


# ---------------------------------------------------------------------------
# Helper: HA-entity tool definitions
# ---------------------------------------------------------------------------

def _build_ha_tools(hass: HomeAssistant) -> list[dict]:
    """Build a minimal set of HA-entity control tool declarations for Gemini."""
    from google.genai import types  # noqa: PLC0415

    # Collect entity IDs exposed to the assistant, grouped by domain.
    light_ids: list[str] = []
    climate_ids: list[str] = []
    switch_ids: list[str] = []
    scene_ids: list[str] = []

    for state in hass.states.async_all():
        domain = state.entity_id.split(".")[0]
        if domain == "light":
            light_ids.append(state.entity_id)
        elif domain == "climate":
            climate_ids.append(state.entity_id)
        elif domain == "switch":
            switch_ids.append(state.entity_id)
        elif domain == "scene":
            scene_ids.append(state.entity_id)

    controllable_ids = light_ids + switch_ids
    all_ids = controllable_ids + climate_ids + scene_ids

    if not all_ids:
        return []

    function_declarations = []

    if controllable_ids:
        function_declarations.append(
            types.FunctionDeclaration(
                name="turn_on",
                description="Turn on a light or switch.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "entity_id": types.Schema(
                            type=types.Type.STRING,
                            description=f"Entity ID of the device. One of: {', '.join(controllable_ids)}",
                        )
                    },
                    required=["entity_id"],
                ),
            )
        )
        function_declarations.append(
            types.FunctionDeclaration(
                name="turn_off",
                description="Turn off a light or switch.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "entity_id": types.Schema(
                            type=types.Type.STRING,
                            description=f"Entity ID of the device. One of: {', '.join(controllable_ids)}",
                        )
                    },
                    required=["entity_id"],
                ),
            )
        )

    if climate_ids:
        function_declarations.append(
            types.FunctionDeclaration(
                name="set_temperature",
                description="Set the target temperature on a climate/thermostat entity.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "entity_id": types.Schema(
                            type=types.Type.STRING,
                            description=f"Entity ID of the thermostat. One of: {', '.join(climate_ids)}",
                        ),
                        "temperature": types.Schema(
                            type=types.Type.NUMBER,
                            description="Target temperature.",
                        ),
                    },
                    required=["entity_id", "temperature"],
                ),
            )
        )

    if scene_ids:
        function_declarations.append(
            types.FunctionDeclaration(
                name="activate_scene",
                description="Activate a Home Assistant scene.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "scene_id": types.Schema(
                            type=types.Type.STRING,
                            description=f"Scene entity ID. One of: {', '.join(scene_ids)}",
                        )
                    },
                    required=["scene_id"],
                ),
            )
        )

    return [types.Tool(function_declarations=function_declarations)]


async def _handle_tool_calls(
    hass: HomeAssistant,
    response,
) -> tuple[str, list[str]]:
    """Execute any tool calls in *response* and return (text, tool_result_messages)."""
    text = (response.text or "").strip()
    tool_results: list[str] = []

    candidates = response.candidates or []
    for candidate in candidates:
        content = candidate.content
        if content is None:
            continue
        for part in content.parts or []:
            if part.function_call is None:
                continue
            name = part.function_call.name
            args = dict(part.function_call.args or {})
            result = await _call_ha_service(hass, name, args)
            tool_results.append(
                f"Tool '{name}' result: {result}"
            )

    return text, tool_results


async def _call_ha_service(
    hass: HomeAssistant,
    tool_name: str,
    args: dict,
) -> str:
    """Dispatch a Gemini tool call to the corresponding HA service."""
    try:
        if tool_name == "turn_on":
            await hass.services.async_call(
                "homeassistant",
                "turn_on",
                {"entity_id": args["entity_id"]},
                blocking=True,
            )
            return f"Turned on {args['entity_id']}."

        if tool_name == "turn_off":
            await hass.services.async_call(
                "homeassistant",
                "turn_off",
                {"entity_id": args["entity_id"]},
                blocking=True,
            )
            return f"Turned off {args['entity_id']}."

        if tool_name == "set_temperature":
            await hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": args["entity_id"],
                    "temperature": args["temperature"],
                },
                blocking=True,
            )
            return f"Set temperature of {args['entity_id']} to {args['temperature']}."

        if tool_name == "activate_scene":
            await hass.services.async_call(
                "scene",
                "turn_on",
                {"entity_id": args["scene_id"]},
                blocking=True,
            )
            return f"Activated scene {args['scene_id']}."

        return f"Unknown tool: {tool_name}"

    except Exception as err:  # noqa: BLE001
        _LOGGER.error("Tool call '%s' failed: %s", tool_name, err)
        return f"Error executing {tool_name}: {err}"
