"""Tests for the rule engine condition evaluation logic."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.services.rule_engine import evaluate_condition, evaluate_conditions


def test_eq_operator():
    assert evaluate_condition({"field": "env", "operator": "eq", "value": "production"}, {"env": "production"})
    assert not evaluate_condition({"field": "env", "operator": "eq", "value": "production"}, {"env": "staging"})


def test_ne_operator():
    assert evaluate_condition({"field": "env", "operator": "ne", "value": "production"}, {"env": "staging"})
    assert not evaluate_condition({"field": "env", "operator": "ne", "value": "production"}, {"env": "production"})


def test_gt_operator():
    assert evaluate_condition({"field": "amount", "operator": "gt", "value": 100}, {"amount": 150})
    assert not evaluate_condition({"field": "amount", "operator": "gt", "value": 100}, {"amount": 50})
    assert not evaluate_condition({"field": "amount", "operator": "gt", "value": 100}, {"amount": 100})


def test_gte_operator():
    assert evaluate_condition({"field": "amount", "operator": "gte", "value": 100}, {"amount": 100})
    assert evaluate_condition({"field": "amount", "operator": "gte", "value": 100}, {"amount": 150})
    assert not evaluate_condition({"field": "amount", "operator": "gte", "value": 100}, {"amount": 50})


def test_lt_operator():
    assert evaluate_condition({"field": "amount", "operator": "lt", "value": 100}, {"amount": 50})
    assert not evaluate_condition({"field": "amount", "operator": "lt", "value": 100}, {"amount": 150})


def test_lte_operator():
    assert evaluate_condition({"field": "amount", "operator": "lte", "value": 100}, {"amount": 100})
    assert evaluate_condition({"field": "amount", "operator": "lte", "value": 100}, {"amount": 50})
    assert not evaluate_condition({"field": "amount", "operator": "lte", "value": 100}, {"amount": 150})


def test_in_operator():
    assert evaluate_condition({"field": "env", "operator": "in", "value": ["staging", "production"]}, {"env": "staging"})
    assert not evaluate_condition({"field": "env", "operator": "in", "value": ["staging", "production"]}, {"env": "dev"})


def test_contains_operator():
    assert evaluate_condition({"field": "name", "operator": "contains", "value": "John"}, {"name": "John Smith"})
    assert not evaluate_condition({"field": "name", "operator": "contains", "value": "Jane"}, {"name": "John Smith"})


def test_missing_field_returns_false():
    assert not evaluate_condition({"field": "missing", "operator": "eq", "value": "x"}, {"other": "y"})


def test_invalid_operator_returns_false():
    assert not evaluate_condition({"field": "x", "operator": "invalid", "value": 1}, {"x": 1})


def test_evaluate_conditions_empty():
    assert evaluate_conditions([], {"any": "params"})


def test_evaluate_conditions_all_match():
    conditions = [
        {"field": "amount", "operator": "gt", "value": 100},
        {"field": "currency", "operator": "eq", "value": "usd"},
    ]
    assert evaluate_conditions(conditions, {"amount": 200, "currency": "usd"})


def test_evaluate_conditions_one_fails():
    conditions = [
        {"field": "amount", "operator": "gt", "value": 100},
        {"field": "currency", "operator": "eq", "value": "usd"},
    ]
    assert not evaluate_conditions(conditions, {"amount": 200, "currency": "eur"})


def test_string_to_number_coercion():
    assert evaluate_condition({"field": "amount", "operator": "gt", "value": 100}, {"amount": "150"})
