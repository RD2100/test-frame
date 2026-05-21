"""FitTrack 模拟云函数服务器

模拟微信云开发后端，用于离线测试。
覆盖: login / getExercises / getPlans / saveWorkout / planTemplates / admin*
"""

import json
import time
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

PORT = 8765  # Same port as demo mock server

# ── 种子数据 ──

CATEGORIES = ["chest", "back", "shoulder", "arm", "leg", "core", "cardio", "stretch"]
DIFFICULTIES = ["beginner", "intermediate", "advanced"]
EQUIPMENTS = ["barbell", "dumbbell", "machine", "cable", "bodyweight", "kettlebell", "band"]

SAMPLE_EXERCISES = [
    {"_id": "ex_001", "name": "杠铃卧推", "category": "chest", "difficulty": "intermediate",
     "equipment": "barbell", "muscleGroups": ["胸大肌", "肱三头肌"], "status": "active"},
    {"_id": "ex_002", "name": "哑铃飞鸟", "category": "chest", "difficulty": "beginner",
     "equipment": "dumbbell", "muscleGroups": ["胸大肌"], "status": "active"},
    {"_id": "ex_003", "name": "引体向上", "category": "back", "difficulty": "intermediate",
     "equipment": "bodyweight", "muscleGroups": ["背阔肌", "肱二头肌"], "status": "active"},
    {"_id": "ex_004", "name": "杠铃深蹲", "category": "leg", "difficulty": "advanced",
     "equipment": "barbell", "muscleGroups": ["股四头肌", "臀大肌"], "status": "active"},
    {"_id": "ex_005", "name": "哑铃弯举", "category": "arm", "difficulty": "beginner",
     "equipment": "dumbbell", "muscleGroups": ["肱二头肌"], "status": "active"},
    {"_id": "ex_006", "name": "哑铃侧平举", "category": "shoulder", "difficulty": "beginner",
     "equipment": "dumbbell", "muscleGroups": ["三角肌中束"], "status": "active"},
    {"_id": "ex_007", "name": "平板支撑", "category": "core", "difficulty": "beginner",
     "equipment": "bodyweight", "muscleGroups": ["腹直肌", "腹横肌"], "status": "active"},
    {"_id": "ex_008", "name": "跑步", "category": "cardio", "difficulty": "beginner",
     "equipment": "other", "muscleGroups": ["心肺系统"], "status": "active"},
    {"_id": "ex_009", "name": "杠铃硬拉", "category": "back", "difficulty": "advanced",
     "equipment": "barbell", "muscleGroups": ["竖脊肌", "臀大肌"], "status": "active"},
    {"_id": "ex_010", "name": "绳索下拉", "category": "arm", "difficulty": "intermediate",
     "equipment": "cable", "muscleGroups": ["肱三头肌"], "status": "inactive"},
    {"_id": "ex_011", "name": "腿举", "category": "leg", "difficulty": "intermediate",
     "equipment": "machine", "muscleGroups": ["股四头肌"], "status": "active"},
    {"_id": "ex_012", "name": "坐姿划船", "category": "back", "difficulty": "intermediate",
     "equipment": "cable", "muscleGroups": ["背阔肌", "菱形肌"], "status": "active"},
]

SAMPLE_PLANS = [
    {"_id": "plan_001", "name": "推拉腿分化", "goal": "hypertrophy", "frequency": 6,
     "days": [{"day": 1, "name": "推日", "exercises": ["ex_001", "ex_002", "ex_006"]},
              {"day": 2, "name": "拉日", "exercises": ["ex_003", "ex_009", "ex_012"]},
              {"day": 3, "name": "腿日", "exercises": ["ex_004", "ex_011"]}],
     "isActive": True},
    {"_id": "plan_002", "name": "全身训练", "goal": "general", "frequency": 3,
     "days": [{"day": 1, "name": "全身A", "exercises": ["ex_001", "ex_003", "ex_004", "ex_005"]}],
     "isActive": False},
]

USERS = {}
WORKOUTS = []


class FitTrackMockHandler(BaseHTTPRequestHandler):
    """模拟 FitTrack 云函数 API"""

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        if path == "/api/login":
            self._handle_login(body)
        elif path == "/api/getExercises":
            self._handle_getExercises(body)
        elif path == "/api/getPlans":
            self._handle_getPlans(body)
        elif path == "/api/saveWorkout":
            self._handle_saveWorkout(body)
        elif path == "/api/planTemplates":
            self._handle_planTemplates(body)
        elif path.startswith("/api/admin"):
            self._handle_admin(path, body)
        else:
            self._json(404, {"code": -1, "message": "Unknown endpoint"})

    # ── Handlers ──

    def _handle_login(self, body):
        openid = body.get("openid", f"mock_openid_{random.randint(1000, 9999)}")
        if openid not in USERS:
            USERS[openid] = {
                "_openid": openid,
                "nickname": f"User_{openid[-4:]}",
                "avatar": "",
                "gender": 0,
                "height": 175,
                "weight": 70,
                "goal": "general",
                "unit": "kg",
                "createdAt": time.time()
            }
        self._json(200, {"code": 0, "openid": openid, "userInfo": USERS[openid]})

    def _handle_getExercises(self, body):
        action = body.get("action", "list")
        data = body.get("data", {})

        if action == "list":
            page = data.get("page", 1)
            page_size = data.get("pageSize", 20)
            category = data.get("category")
            items = [e for e in SAMPLE_EXERCISES if e["status"] == "active"]
            if category:
                items = [e for e in items if e["category"] == category]
            start = (page - 1) * page_size
            self._json(200, {
                "code": 0, "data": {
                    "items": items[start:start + page_size],
                    "total": len(items), "page": page, "pageSize": page_size
                }
            })

        elif action == "detail":
            ex_id = data.get("id")
            ex = next((e for e in SAMPLE_EXERCISES if e["_id"] == ex_id), None)
            if ex:
                self._json(200, {"code": 0, "data": ex})
            else:
                self._json(200, {"code": -1, "message": "Action does not exist"})

        elif action == "search":
            keyword = data.get("keyword", "")
            items = [e for e in SAMPLE_EXERCISES
                     if e["status"] == "active" and keyword.lower() in e["name"].lower()]
            self._json(200, {"code": 0, "data": items})

        elif action == "byCategory":
            category = data.get("category")
            items = [e for e in SAMPLE_EXERCISES
                     if e["status"] == "active" and (not category or e["category"] == category)]
            self._json(200, {"code": 0, "data": items})

        else:
            self._json(200, {"code": -1, "message": "Unknown action"})

    def _handle_getPlans(self, body):
        user_openid = body.get("openid", "mock_user")
        active_only = body.get("activeOnly", False)
        plans = [p for p in SAMPLE_PLANS if not active_only or p["isActive"]]
        self._json(200, {"code": 0, "data": {"plans": plans, "total": len(plans)}})

    def _handle_saveWorkout(self, body):
        workout = {
            "id": f"wo_{len(WORKOUTS) + 1}",
            "planId": body.get("planId"),
            "exercises": body.get("exercises", []),
            "startTime": time.time(),
            "endTime": time.time() + body.get("duration", 1800),
            "volume": body.get("volume", 0)
        }
        WORKOUTS.append(workout)
        self._json(200, {"code": 0, "data": {"id": workout["id"]}})

    def _handle_planTemplates(self, body):
        templates = [
            {"id": "tpl_001", "name": "推拉腿分化", "goal": "hypertrophy", "frequency": 6},
            {"id": "tpl_002", "name": "上下肢分化", "goal": "strength", "frequency": 4},
            {"id": "tpl_003", "name": "全身训练", "goal": "general", "frequency": 3},
            {"id": "tpl_004", "name": "减脂循环", "goal": "fat_loss", "frequency": 5},
        ]
        self._json(200, {"code": 0, "data": templates})

    def _handle_admin(self, path, body):
        if "Exercises" in path:
            items = SAMPLE_EXERCISES
            self._json(200, {"code": 0, "data": {"items": items, "total": len(items)}})
        elif "Plans" in path:
            self._json(200, {"code": 0, "data": {"items": SAMPLE_PLANS, "total": len(SAMPLE_PLANS)}})
        elif "Stats" in path:
            self._json(200, {"code": 0, "data": {
                "totalUsers": len(USERS),
                "totalWorkouts": len(WORKOUTS),
                "totalExercises": len([e for e in SAMPLE_EXERCISES if e["status"] == "active"]),
                "totalPlans": len(SAMPLE_PLANS)
            }})
        elif "Seed" in path:
            self._json(200, {"code": 0, "data": {"imported": 85}})
        else:
            self._json(200, {"code": 0, "data": {}})

    # ── Helpers ──

    def _read_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(length)) if length > 0 else {}
        except Exception:
            return {}

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, format, *args):
        pass


def start_server(port=PORT):
    server = HTTPServer(("127.0.0.1", port), FitTrackMockHandler)
    print(f"[FitTrack Mock] http://127.0.0.1:{port}")
    return server


if __name__ == "__main__":
    srv = start_server()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
