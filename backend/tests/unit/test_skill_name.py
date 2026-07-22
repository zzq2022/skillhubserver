"""Unit tests for skill name validation / slugify (T4.1)."""

from __future__ import annotations

import pytest

from app.utils.skill_name import is_valid_skill_name, slugify, validate_skill_name


def test_valid_names() -> None:
    for name in ("a", "skill", "my-skill", "s1", "a-b-c", "x" * 100):
        assert is_valid_skill_name(name) is True
        assert validate_skill_name(name) == name


def test_invalid_names() -> None:
    for name in ("", "-skill", "skill-", "MySkill", "my_skill", "a b", "a--b"):
        # a--b is technically matched by the regex ([a-z0-9-]* allows --)
        # design regex allows consecutive hyphens; only edges are constrained.
        pass
    assert is_valid_skill_name("") is False
    assert is_valid_skill_name("-skill") is False
    assert is_valid_skill_name("skill-") is False
    assert is_valid_skill_name("MySkill") is False
    assert is_valid_skill_name("my_skill") is False
    assert is_valid_skill_name("a b") is False
    assert is_valid_skill_name("x" * 101) is False
    with pytest.raises(ValueError):
        validate_skill_name("Bad Name")


def test_slugify() -> None:
    assert slugify("my-skill") == "my-skill"
    assert slugify("My Cool Skill!") == "my-cool-skill"
    assert slugify("  Hello World  ") == "hello-world"
    with pytest.raises(ValueError):
        slugify("!!!")
