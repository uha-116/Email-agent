import importlib
import sys
import types


def test_safe_import_llm_module_with_stubbed_google_stack(monkeypatch, scenario_printer):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    sys.modules.pop("backend.email_analyser.llm_gemini", None)

    module = importlib.import_module("backend.email_analyser.llm_gemini")

    assert module.API_KEY == "test-key"
    assert hasattr(module, "call_llm")
    scenario_printer(
        "Safe import of llm_gemini",
        "Import-time Google dependencies replaced with stubs",
        "Module should import without touching real Gemini APIs",
        "Module imported successfully with stubbed API key",
    )


def test_safe_import_query_engine_intent_to_sql_without_real_db(scenario_printer):
    fake_sbert = types.ModuleType("backend.query_engine.sbert_model")

    class DummyMatcher:
        def find_top_matches(self, question, top_k=1):
            return [{"question": "any deadlines pending", "score": 0.99}]

    fake_sbert.SBERTMatcher = DummyMatcher
    sys.modules["backend.query_engine.sbert_model"] = fake_sbert

    fake_entity_cache = types.ModuleType("backend.query_engine.entity_cache")

    class DummyEntityCache:
        def load_from_db(self):
            return None

        def match_company(self, text):
            return None

        def match_role(self, text):
            return None

        def match_location(self, text):
            return None

    fake_entity_cache.EntityCache = DummyEntityCache
    sys.modules["backend.query_engine.entity_cache"] = fake_entity_cache

    sys.modules.pop("backend.query_engine.intent_to_sql", None)
    module = importlib.import_module("backend.query_engine.intent_to_sql")

    result = module.resolve_user_question("any deadlines pending")

    assert result["matched_question"] == "any deadlines pending"
    assert "count_sql" in result
    scenario_printer(
        "Safe import of intent_to_sql",
        "SBERT and EntityCache replaced with stubs before import",
        "Module should import and resolve a question without real DB/model access",
        "Module imported safely and returned SQL result",
    )
