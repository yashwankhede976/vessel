"""API tests for the AI chatbot endpoint.

These NEVER call the real OpenAI API — the OpenAI phrasing function is patched.
They verify: grounded success (mocked LLM), graceful fallback when no key,
validation errors, OpenAI error handling, context passing, and that the API key
never appears in a response.
"""
from decimal import Decimal
from unittest import mock

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Origin, Port, Route, Vessel
from apps.operations.models import FreightForecast
from datetime import date, timedelta

CHATBOT = "apps.decisions.services.chatbot"
FAKE_KEY = "sk-test-DO-NOT-USE-1234567890"


class ChatApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.origin, _ = Origin.objects.get_or_create(
            name="Australia", defaults={"country": "Australia"}
        )
        cls.port, _ = Port.objects.get_or_create(
            name="Paradip", country="India",
            defaults={"latitude": Decimal("20.26"), "longitude": Decimal("86.67")},
        )
        cls.route, _ = Route.objects.get_or_create(
            origin=cls.origin, destination_port=cls.port,
            defaults={"distance_nm": Decimal("6500")},
        )
        Vessel.objects.create(
            imo="4300001", name="Pana Fit", vessel_type=Vessel.VesselType.PANAMAX,
            dwt=Decimal("80000"), loa=Decimal("229"), beam=Decimal("32"),
            draft=Decimal("13.5"), speed=Decimal("13.0"),
            availability_status=Vessel.AvailabilityStatus.OPEN,
        )
        FreightForecast.objects.create(
            route=cls.route, vessel_type=Vessel.VesselType.PANAMAX,
            generated_at=timezone.now(), target_date=date.today() + timedelta(days=10),
            horizon=FreightForecast.Horizon.SHORT_TERM,
            predicted_rate_per_tonne=Decimal("22.00"),
            lower_bound=Decimal("20.00"), upper_bound=Decimal("24.00"),
            confidence=Decimal("0.80"), model_name="freight_gbm_xgboost",
            model_version="0.2.0",
        )

    def _url(self):
        return reverse("v1:chat:chat")

    # ---- success with a mocked OpenAI response ----
    @override_settings(OPENAI={"API_KEY": FAKE_KEY, "MODEL": "gpt-4o-mini", "TIMEOUT": 5, "MAX_OUTPUT_TOKENS": 100})
    def test_success_with_mocked_openai(self):
        with mock.patch(f"{CHATBOT}._openai_phrase", return_value="Grounded LLM phrasing.") as m:
            resp = self.client.post(
                self._url(),
                {"message": "Should I fix Australia to Paradip?"},
                format="json",
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertEqual(data["answer"], "Grounded LLM phrasing.")
        self.assertIn("conversation_id", data)
        self.assertTrue(len(data["sources"]) > 0)
        self.assertTrue(len(data["data_used"]) > 0)
        self.assertIn("confidence", data)
        m.assert_called_once()

    # ---- graceful fallback when no API key ----
    @override_settings(OPENAI={"API_KEY": "", "MODEL": "gpt-4o-mini", "TIMEOUT": 5, "MAX_OUTPUT_TOKENS": 100})
    def test_fallback_when_no_key(self):
        resp = self.client.post(
            self._url(), {"message": "Should I fix Australia to Paradip?"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        # The deterministic grounded fallback is returned (mentions the lane).
        self.assertIn("Australia", data["answer"])
        self.assertIn("Paradip", data["answer"])

    # ---- invalid request ----
    def test_empty_message_returns_400(self):
        resp = self.client.post(self._url(), {"message": "   "}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(resp.json()["success"])

    def test_missing_message_returns_400(self):
        resp = self.client.post(self._url(), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ---- OpenAI error/timeout handled -> fallback, still 200 ----
    @override_settings(OPENAI={"API_KEY": FAKE_KEY, "MODEL": "gpt-4o-mini", "TIMEOUT": 5, "MAX_OUTPUT_TOKENS": 100})
    def test_openai_error_falls_back_gracefully(self):
        # _openai_phrase swallows exceptions and returns None; simulate that.
        with mock.patch(f"{CHATBOT}._openai_phrase", return_value=None):
            resp = self.client.post(
                self._url(), {"message": "Should I fix Australia to Paradip?"}, format="json"
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()["data"]
        self.assertIn("Australia", data["answer"])

    # ---- context passing ----
    @override_settings(OPENAI={"API_KEY": "", "MODEL": "gpt-4o-mini", "TIMEOUT": 5, "MAX_OUTPUT_TOKENS": 100})
    def test_context_overrides_lane(self):
        resp = self.client.post(
            self._url(),
            {"message": "What is the recommendation?",
             "context": {"origin": "Australia", "destination": "Paradip"}},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("Paradip", resp.json()["data"]["answer"])

    # ---- the API key must NEVER appear in the response ----
    @override_settings(OPENAI={"API_KEY": FAKE_KEY, "MODEL": "gpt-4o-mini", "TIMEOUT": 5, "MAX_OUTPUT_TOKENS": 100})
    def test_api_key_never_in_response(self):
        with mock.patch(f"{CHATBOT}._openai_phrase", return_value="ok"):
            resp = self.client.post(
                self._url(), {"message": "Should I fix Australia to Paradip?"}, format="json"
            )
        self.assertNotIn(FAKE_KEY, resp.content.decode())

    # ---- conversation reset ----
    def test_reset_conversation(self):
        resp = self.client.delete(self._url() + "?conversation_id=xyz")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.json()["data"]["reset"])

    def test_reset_requires_conversation_id(self):
        resp = self.client.delete(self._url())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class ChatIndianScopeTests(APITestCase):
    """Verify the chatbot is strictly specialized for India East Coast bulk-cargo
    procurement and that answers use actual backend data (never invented)."""

    @classmethod
    def setUpTestData(cls):
        cls.origin_au, _ = Origin.objects.get_or_create(
            name="Australia", defaults={"country": "Australia"}
        )
        cls.origin_id, _ = Origin.objects.get_or_create(
            name="Indonesia", defaults={"country": "Indonesia"}
        )
        cls.paradip, _ = Port.objects.get_or_create(
            name="Paradip", country="India",
            defaults={"latitude": Decimal("20.26"), "longitude": Decimal("86.67")},
        )
        cls.route_au, _ = Route.objects.get_or_create(
            origin=cls.origin_au, destination_port=cls.paradip,
            defaults={"distance_nm": Decimal("6500")},
        )
        Route.objects.get_or_create(
            origin=cls.origin_id, destination_port=cls.paradip,
            defaults={"distance_nm": Decimal("3100")},
        )
        Vessel.objects.create(
            imo="4400001", name="Pana Fit", vessel_type=Vessel.VesselType.PANAMAX,
            dwt=Decimal("80000"), loa=Decimal("229"), beam=Decimal("32"),
            draft=Decimal("13.5"), speed=Decimal("13.0"),
            availability_status=Vessel.AvailabilityStatus.OPEN,
        )
        # A REAL stored forecast so the freight figure is labelled FORECAST with
        # a source timestamp — proving the answer uses actual backend data.
        cls.fc = FreightForecast.objects.create(
            route=cls.route_au, vessel_type=Vessel.VesselType.PANAMAX,
            generated_at=timezone.now(), target_date=date.today() + timedelta(days=10),
            horizon=FreightForecast.Horizon.SHORT_TERM,
            predicted_rate_per_tonne=Decimal("22.00"),
            lower_bound=Decimal("20.00"), upper_bound=Decimal("24.00"),
            confidence=Decimal("0.80"), model_name="freight_gbm_xgboost",
            model_version="0.2.0",
        )

    def _url(self):
        return reverse("v1:chat:chat")

    def _ask(self, message, conversation_id=None, context=None):
        body = {"message": message}
        if conversation_id:
            body["conversation_id"] = conversation_id
        if context:
            body["context"] = context
        resp = self.client.post(self._url(), body, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        return resp.json()["data"]

    # ---- scope: off-topic is rejected with the exact message ----
    @override_settings(OPENAI={"API_KEY": "", "MODEL": "gpt-4o-mini", "TIMEOUT": 5, "MAX_OUTPUT_TOKENS": 100})
    def test_out_of_scope_question_is_rejected(self):
        d = self._ask("What is the capital of France?")
        self.assertEqual(
            d["answer"],
            "This chatbot is specialized in overseas bulk-cargo procurement and "
            "vessel chartering for India's East Coast ports.",
        )
        self.assertEqual(d["sources"], [])

    @override_settings(OPENAI={"API_KEY": "", "MODEL": "gpt-4o-mini", "TIMEOUT": 5, "MAX_OUTPUT_TOKENS": 100})
    def test_generic_coding_question_is_rejected(self):
        d = self._ask("Write me a Python function to sort a list.")
        self.assertIn("specialized in overseas bulk-cargo", d["answer"])

    # ---- India scenarios are answered and grounded ----
    @override_settings(OPENAI={"API_KEY": "", "MODEL": "gpt-4o-mini", "TIMEOUT": 5, "MAX_OUTPUT_TOKENS": 100})
    def test_fix_australia_to_paradip_uses_real_forecast(self):
        d = self._ask("Should I fix Australia to Paradip?")
        # The answer names the Indian lane and cites the REAL stored working rate,
        # not an invented number.
        self.assertIn("Paradip", d["answer"])
        self.assertIn("22.00", d["answer"])  # from the stored FreightForecast
        self.assertIn("FORECAST", d["answer"])

    @override_settings(OPENAI={"API_KEY": "", "MODEL": "gpt-4o-mini", "TIMEOUT": 5, "MAX_OUTPUT_TOKENS": 100})
    def test_vizag_alias_resolves_to_visakhapatnam(self):
        d = self._ask("Is Vizag congestion increasing?")
        self.assertIn("Visakhapatnam", d["answer"])

    @override_settings(OPENAI={"API_KEY": "", "MODEL": "gpt-4o-mini", "TIMEOUT": 5, "MAX_OUTPUT_TOKENS": 100})
    def test_vessel_and_tonnage_question_in_scope(self):
        d = self._ask("Which vessel is best for 100000 MT coal to Dhamra?")
        self.assertIn("Dhamra", d["answer"])
        self.assertNotIn("specialized in overseas", d["answer"])

    # ---- data labels are exposed to the model grounding ----
    @override_settings(OPENAI={"API_KEY": FAKE_KEY, "MODEL": "gpt-4o-mini", "TIMEOUT": 5, "MAX_OUTPUT_TOKENS": 100})
    def test_grounding_carries_data_labels_and_scope(self):
        captured = {}

        def _fake_phrase(message, grounding, history):
            captured["grounding"] = grounding
            return "ok"

        with mock.patch(f"{CHATBOT}._openai_phrase", side_effect=_fake_phrase):
            self._ask("Should I fix Australia to Paradip?")
        g = captured["grounding"]
        self.assertTrue(g["india_scope"])
        self.assertEqual(g["freight_forecast"]["label"], "FORECAST")
        self.assertIsNotNone(g["freight_forecast"]["generated_at"])
        self.assertIn("data_labels", g)
        self.assertEqual(g["lane"]["destination"], "Paradip")

    # ---- conversation context: follow-up keeps the prior comparison ----
    @override_settings(OPENAI={"API_KEY": "", "MODEL": "gpt-4o-mini", "TIMEOUT": 5, "MAX_OUTPUT_TOKENS": 100})
    def test_followup_inherits_conversation_lane(self):
        first = self._ask("Compare Australia and Indonesia to Paradip.")
        cid = first["conversation_id"]
        # A bare follow-up would be off-topic on its own, but the conversation
        # lane keeps it in scope and grounded.
        d = self._ask("Which is cheaper?", conversation_id=cid)
        self.assertNotIn("specialized in overseas", d["answer"])
        self.assertIn("Paradip", d["answer"])

    # ---- Indian data unavailable message when grounding cannot be produced ----
    @override_settings(OPENAI={"API_KEY": "", "MODEL": "gpt-4o-mini", "TIMEOUT": 5, "MAX_OUTPUT_TOKENS": 100})
    def test_indian_data_unavailable_message(self):
        # When the decision engine cannot produce grounded data, the chatbot is
        # honest rather than guessing.
        from apps.decisions.services.decision_engine import DecisionError

        with mock.patch(f"{CHATBOT}._grounded_data", side_effect=DecisionError("no route")):
            d = self._ask("Should I fix Australia to Paradip?")
        self.assertEqual(d["answer"], "Indian data for this request is currently unavailable.")
        self.assertEqual(d["sources"], [])
