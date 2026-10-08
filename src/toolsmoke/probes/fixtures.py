"""Shared tool definitions and prompts used by the probes."""

WEATHER_SCHEMA = {
    "type": "object",
    "properties": {
        "city": {"type": "string", "description": "City name, e.g. Paris"},
        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "description": "Temperature unit"},
    },
    "required": ["city"],
    "additionalProperties": False,
}

TIME_SCHEMA = {
    "type": "object",
    "properties": {"timezone": {"type": "string", "description": "IANA timezone, e.g. Europe/Paris"}},
    "required": ["timezone"],
    "additionalProperties": False,
}

WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": WEATHER_SCHEMA,
    },
}

TIME_TOOL = {
    "type": "function",
    "function": {
        "name": "get_time",
        "description": "Get the current local time in a timezone.",
        "parameters": TIME_SCHEMA,
    },
}

TOOLS = [WEATHER_TOOL, TIME_TOOL]
SCHEMAS = {"get_weather": WEATHER_SCHEMA, "get_time": TIME_SCHEMA}

SYSTEM_TOOLS = "You are a helpful assistant. Use the provided tools whenever they are relevant."

WEATHER_RESULT_PARIS = '{"city": "Paris", "temp_c": 23, "condition": "sunny"}'
WEATHER_RESULT_TOKYO = '{"city": "Tokyo", "temp_c": 17, "condition": "rain"}'

STRUCTURED_SCHEMA = {
    "type": "object",
    "properties": {
        "city": {"type": "string"},
        "country": {"type": "string"},
        "population_millions": {"type": "number"},
        "landmarks": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 5},
    },
    "required": ["city", "country", "population_millions", "landmarks"],
    "additionalProperties": False,
}
