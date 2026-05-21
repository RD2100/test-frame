"""FitTrack 核心 API 测试 — 模拟云函数调用

覆盖: login / getExercises / getPlans / saveWorkout / planTemplates
"""

import requests
import pytest

BASE_URL = "http://127.0.0.1:8765"
TOKEN = None  # Will be set after login


# ═══════════════════════════════════════════════
# Login 测试
# ═══════════════════════════════════════════════

class TestLogin:
    def test_login_creates_user(self):
        resp = requests.post(f"{BASE_URL}/api/login",
                             json={"openid": "test_user_001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "openid" in data
        assert data["userInfo"] is not None
        assert data["userInfo"]["nickname"].startswith("User_")

    def test_login_returns_existing_user(self):
        # Login twice with same openid → should return existing
        resp1 = requests.post(f"{BASE_URL}/api/login",
                              json={"openid": "test_user_002"})
        resp2 = requests.post(f"{BASE_URL}/api/login",
                              json={"openid": "test_user_002"})
        assert resp1.json()["userInfo"]["nickname"] == resp2.json()["userInfo"]["nickname"]

    def test_login_user_has_required_fields(self):
        resp = requests.post(f"{BASE_URL}/api/login",
                             json={"openid": "test_user_003"})
        user = resp.json()["userInfo"]
        required_fields = ["_openid", "nickname", "height", "weight", "goal", "unit"]
        for field in required_fields:
            assert field in user, f"Missing required field: {field}"


# ═══════════════════════════════════════════════
# getExercises 测试
# ═══════════════════════════════════════════════

class TestGetExercises:
    def test_list_all_active(self):
        resp = requests.post(f"{BASE_URL}/api/getExercises",
                             json={"action": "list", "data": {}})
        data = resp.json()
        assert data["code"] == 0
        items = data["data"]["items"]
        total = data["data"]["total"]
        assert total >= 10  # 11 active exercises in seed data
        assert all(e["status"] == "active" for e in items)
        assert all("name" in e and "category" in e for e in items)

    def test_list_by_category(self):
        resp = requests.post(f"{BASE_URL}/api/getExercises",
                             json={"action": "list", "data": {"category": "chest"}})
        items = resp.json()["data"]["items"]
        assert all(e["category"] == "chest" for e in items)
        assert len(items) >= 2  # 2 chest exercises

    def test_list_pagination(self):
        resp = requests.post(f"{BASE_URL}/api/getExercises",
                             json={"action": "list", "data": {"page": 1, "pageSize": 3}})
        data = resp.json()["data"]
        assert len(data["items"]) <= 3
        assert data["page"] == 1

    def test_detail_existing(self):
        resp = requests.post(f"{BASE_URL}/api/getExercises",
                             json={"action": "detail", "data": {"id": "ex_001"}})
        ex = resp.json()["data"]
        assert ex["name"] == "杠铃卧推"
        assert ex["category"] == "chest"
        assert ex["difficulty"] == "intermediate"

    def test_detail_not_found(self):
        resp = requests.post(f"{BASE_URL}/api/getExercises",
                             json={"action": "detail", "data": {"id": "nonexistent"}})
        assert resp.json()["code"] == -1

    def test_detail_missing_id(self):
        resp = requests.post(f"{BASE_URL}/api/getExercises",
                             json={"action": "detail", "data": {}})
        assert resp.json()["code"] == -1

    def test_search_finds_match(self):
        resp = requests.post(f"{BASE_URL}/api/getExercises",
                             json={"action": "search", "data": {"keyword": "杠铃"}})
        items = resp.json()["data"]
        assert all("杠铃" in e["name"] for e in items)
        assert len(items) >= 2  # 杠铃卧推 + 杠铃深蹲 + 杠铃硬拉

    def test_by_category_returns_all_chest(self):
        resp = requests.post(f"{BASE_URL}/api/getExercises",
                             json={"action": "byCategory", "data": {"category": "leg"}})
        items = resp.json()["data"]
        assert all(e["category"] == "leg" for e in items)

    def test_unknown_action(self):
        resp = requests.post(f"{BASE_URL}/api/getExercises",
                             json={"action": "invalidAction", "data": {}})
        assert resp.json()["code"] == -1


# ═══════════════════════════════════════════════
# getPlans 测试
# ═══════════════════════════════════════════════

class TestGetPlans:
    def test_list_all_plans(self):
        resp = requests.post(f"{BASE_URL}/api/getPlans",
                             json={"openid": "test_user"})
        data = resp.json()
        assert data["code"] == 0
        plans = data["data"]["plans"]
        assert len(plans) >= 2
        for plan in plans:
            assert "name" in plan
            assert "goal" in plan
            assert "days" in plan

    def test_active_only(self):
        resp = requests.post(f"{BASE_URL}/api/getPlans",
                             json={"openid": "test_user", "activeOnly": True})
        plans = resp.json()["data"]["plans"]
        assert all(p["isActive"] for p in plans)

    def test_plan_has_valid_structure(self):
        resp = requests.post(f"{BASE_URL}/api/getPlans",
                             json={"openid": "test_user"})
        plan = resp.json()["data"]["plans"][0]
        for day in plan["days"]:
            assert "day" in day, "Day missing day number"
            assert "name" in day, "Day missing name"
            assert "exercises" in day, "Day missing exercises"
            assert len(day["exercises"]) > 0, f"Day {day['day']} has no exercises"


# ═══════════════════════════════════════════════
# saveWorkout 测试
# ═══════════════════════════════════════════════

class TestSaveWorkout:
    def test_save_valid_workout(self):
        resp = requests.post(f"{BASE_URL}/api/saveWorkout",
                             json={
                                 "planId": "plan_001",
                                 "exercises": [
                                     {"exerciseId": "ex_001", "sets": [
                                         {"reps": 10, "weight": 60},
                                         {"reps": 8, "weight": 60},
                                     ]}
                                 ],
                                 "duration": 1800,
                                 "volume": 1200
                             })
        assert resp.status_code == 200
        assert resp.json()["code"] == 0
        assert "id" in resp.json()["data"]

    def test_save_empty_workout(self):
        resp = requests.post(f"{BASE_URL}/api/saveWorkout",
                             json={"planId": None, "exercises": [], "duration": 0, "volume": 0})
        assert resp.json()["code"] == 0


# ═══════════════════════════════════════════════
# planTemplates 测试
# ═══════════════════════════════════════════════

class TestPlanTemplates:
    def test_list_templates(self):
        resp = requests.post(f"{BASE_URL}/api/planTemplates", json={})
        templates = resp.json()["data"]
        assert len(templates) >= 4
        goals = [t["goal"] for t in templates]
        assert "hypertrophy" in goals
        assert "fat_loss" in goals
        assert "general" in goals


# ═══════════════════════════════════════════════
# Admin API 测试
# ═══════════════════════════════════════════════

class TestAdmin:
    def test_stats_endpoint(self):
        resp = requests.post(f"{BASE_URL}/api/adminStats", json={})
        data = resp.json()["data"]
        assert "totalExercises" in data
        assert data["totalExercises"] >= 10

    def test_seed_endpoint(self):
        resp = requests.post(f"{BASE_URL}/api/adminSeed", json={})
        assert resp.json()["data"]["imported"] > 0
