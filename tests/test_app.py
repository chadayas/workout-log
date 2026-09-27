import tempfile
import unittest
from unittest.mock import patch

import app as workout_app


class WorkoutLogTestCase(unittest.TestCase):
    def setUp(self):
        self.env_patcher = patch.dict(
            workout_app.os.environ,
            {"WORKOUT_LOG_API_TOKEN": "test-api-token"},
        )
        self.env_patcher.start()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = workout_app.DB_PATH
        workout_app.DB_PATH = f"{self.temp_dir.name}/workout-log.sqlite"
        workout_app.app.config.update(TESTING=True)
        self.client = workout_app.app.test_client()

        self.client.environ_base["HTTP_X_API_KEY"] = "test-api-token"

    def tearDown(self):
        workout_app.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()
        self.env_patcher.stop()

    def test_api_requires_token_and_publishes_action_schema(self):
        unauthorized = self.client.get(
            "/api/daily?date=2026-09-25",
            headers={"X-API-Key": ""},
        )
        self.assertEqual(unauthorized.status_code, 401)

        with patch.dict(
            workout_app.os.environ,
            {"PUBLIC_BASE_URL": "https://fitness.example.com"},
        ):
            schema_response = self.client.get(
                "/openapi.json",
                headers={"X-API-Key": ""},
            )
        self.assertEqual(schema_response.status_code, 200)
        schema = schema_response.get_json()
        self.assertEqual(schema["servers"][0]["url"], "https://fitness.example.com")
        self.assertEqual(
            schema["components"]["securitySchemes"]["ApiKeyAuth"]["name"],
            "X-API-Key",
        )
        operations = {
            operation["operationId"]
            for path in schema["paths"].values()
            for operation in path.values()
        }
        self.assertEqual(
            operations,
            {
                "logFood",
                "getExercises",
                "logExercise",
                "logBodyWeight",
                "getDailyDashboard",
            },
        )

    def test_food_totals_and_default_calorie_target(self):
        response = self.client.post(
            "/api/foods",
            json={
                "date": "2026-09-25",
                "food_name": "Chicken burrito bowl",
                "calories": 720,
                "protein_g": 52,
                "carbs_g": 78,
                "fat_g": 21,
            },
        )
        self.assertEqual(response.status_code, 201)

        daily = self.client.get("/api/daily?date=2026-09-25").get_json()
        self.assertEqual(daily["calories"], 720)
        self.assertEqual(daily["protein_g"], 52)
        self.assertEqual(daily["carbs_g"], 78)
        self.assertEqual(daily["fat_g"], 21)
        self.assertEqual(
            self.client.get("/api/settings/calorie-target").get_json()["calorie_target"],
            2600,
        )

    def test_chat_logs_food_weight_and_merges_matching_sets(self):
        first_actions = {
            "reply": "Logged your meal, weigh-in, and bench set.",
            "actions": [
                {
                    "type": "food",
                    "date": "2026-09-25",
                    "food_name": "Greek yogurt",
                    "calories": 180,
                    "protein_g": 20,
                    "carbs_g": 16,
                    "fat_g": 4,
                },
                {
                    "type": "exercise",
                    "date": "2026-09-25",
                    "exercise_name": "bench press",
                    "weight_lbs": 225,
                    "reps": 10,
                    "sets": 1,
                },
                {
                    "type": "weight",
                    "date": "2026-09-25",
                    "body_weight_lbs": 184.2,
                },
            ],
        }
        second_actions = {
            "reply": "Added another matching bench set.",
            "actions": [first_actions["actions"][1]],
        }

        with patch.object(
            workout_app,
            "request_gpt_actions",
            side_effect=[first_actions, second_actions],
        ):
            first = self.client.post(
                "/api/chat",
                json={"date": "2026-09-25", "message": "Log my meal, weight, and set"},
            )
            second = self.client.post(
                "/api/chat",
                json={"date": "2026-09-25", "message": "Same bench set again"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        exercises = self.client.get("/api/exercises?date=2026-09-25").get_json()
        self.assertEqual(len(exercises), 1)
        self.assertEqual(exercises[0]["exercise_name"], "Bench Press")
        self.assertEqual(exercises[0]["sets"], 2)
        daily = self.client.get("/api/daily?date=2026-09-25").get_json()
        self.assertEqual(daily["body_weight_lbs"], 184.2)
        self.assertEqual(daily["calories"], 180)

    def test_invalid_chat_action_rolls_back_every_action(self):
        parsed = {
            "reply": "",
            "actions": [
                {
                    "type": "food",
                    "date": "2026-09-25",
                    "food_name": "Apple",
                    "calories": 95,
                    "protein_g": 0.5,
                    "carbs_g": 25,
                    "fat_g": 0.3,
                },
                {
                    "type": "exercise",
                    "date": "2026-09-25",
                    "exercise_name": "bench press",
                    "weight_lbs": 225,
                    "reps": 10,
                    "sets": 0,
                },
            ],
        }
        with patch.object(workout_app, "request_gpt_actions", return_value=parsed):
            response = self.client.post(
                "/api/chat",
                json={"date": "2026-09-25", "message": "bad batch"},
            )

        self.assertEqual(response.status_code, 502)
        foods = self.client.get("/api/foods?date=2026-09-25").get_json()
        self.assertEqual(foods["entries"], [])


if __name__ == "__main__":
    unittest.main()
