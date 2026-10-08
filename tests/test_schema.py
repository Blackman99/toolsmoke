from toolsmoke.probes.fixtures import STRUCTURED_SCHEMA, WEATHER_SCHEMA
from toolsmoke.schema import sample, validate


def test_valid_weather_args():
    assert validate({"city": "Paris", "unit": "celsius"}, WEATHER_SCHEMA) == []


def test_missing_required_and_extra_and_enum():
    errs = validate({"unit": "kelvin", "country": "FR"}, WEATHER_SCHEMA)
    joined = " ".join(errs)
    assert "missing required property 'city'" in joined
    assert "kelvin" in joined
    assert "unexpected property 'country'" in joined


def test_type_mismatch_and_bool_is_not_number():
    assert validate("x", {"type": "object"})
    assert validate(True, {"type": "number"})
    assert validate(3, {"type": "integer"}) == []
    assert validate(3.5, {"type": "integer"})
    assert validate(None, {"type": ["string", "null"]}) == []


def test_arrays_and_bounds():
    s = {"type": "array", "items": {"type": "integer", "minimum": 0}, "minItems": 1, "maxItems": 2}
    assert validate([1, 2], s) == []
    assert validate([], s)
    assert validate([1, 2, 3], s)
    assert validate([-1], s)


def test_anyof_and_const():
    s = {"anyOf": [{"type": "string"}, {"type": "integer"}]}
    assert validate("a", s) == [] and validate(1, s) == []
    assert validate(1.5, s)
    assert validate("b", {"const": "a"})


def test_sample_satisfies_schema():
    for schema in (WEATHER_SCHEMA, STRUCTURED_SCHEMA):
        assert validate(sample(schema), schema) == []
    assert sample(STRUCTURED_SCHEMA, {"city": "Paris"})["city"] == "Paris"
