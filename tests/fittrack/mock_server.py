"""FitTrack 模拟云函数服务器 — 覆盖全部12个云函数

模拟微信云开发后端，用于离线测试。
覆盖: login / getExercises / getPlans / saveWorkout / planTemplates / seedExercises
+ adminAuth / adminExercises / adminPlans / adminUsers / adminStats / adminSeed
"""

import json
import time
import random
import hashlib
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

PORT = 8765

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
     "isActive": True, "isTemplate": True, "createdBy": "admin_001",
     "assignedTo": [], "createdAt": time.time() - 86400 * 30},
    {"_id": "plan_002", "name": "全身训练", "goal": "general", "frequency": 3,
     "days": [{"day": 1, "name": "全身A", "exercises": ["ex_001", "ex_003", "ex_004", "ex_005"]}],
     "isActive": False, "isTemplate": False, "createdBy": "mock_openid_1001",
     "assignedTo": [], "createdAt": time.time() - 86400 * 15},
]

# ── 运行时状态 ──

USERS = {}
WORKOUTS = []
ADMINS = {
    "admin_001": {
        "_id": "admin_001", "username": "admin", "password": hashlib.sha256("admin123".encode()).hexdigest(),
        "role": "super_admin", "createdAt": time.time() - 86400 * 90
    }
}
ADMIN_TOKENS = {}  # token -> admin_id
EXERCISES_DB = list(SAMPLE_EXERCISES)
PLANS_DB = list(SAMPLE_PLANS)
PERSONAL_RECORDS = {}  # openid -> { exerciseId -> { weight, reps, volume, date } }
BODY_METRICS_DB = {}  # openid -> [{ date, weight, bodyFat, ... }]
SEED_STATS = {"imported": 85, "lastImport": time.time() - 86400 * 7}
_next_id = [100]  # 可变计数器，用于生成唯一ID


def _gen_id(prefix="id"):
    _next_id[0] += 1
    return f"{prefix}_{_next_id[0]:04d}"


def _make_token(admin_id):
    """生成简单JWT-like token"""
    payload = f"{admin_id}:{time.time()}:{random.randint(10000, 99999)}"
    token = base64.b64encode(payload.encode()).decode()
    ADMIN_TOKENS[token] = admin_id
    return token


def _verify_token(token):
    """验证token，返回admin_id或None"""
    return ADMIN_TOKENS.get(token)


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
        elif path == "/api/seedExercises":
            self._handle_seedExercises(body)
        elif path == "/api/adminAuth":
            self._handle_adminAuth(body)
        elif path == "/api/adminExercises":
            self._handle_adminExercises(body)
        elif path == "/api/adminPlans":
            self._handle_adminPlans(body)
        elif path == "/api/adminUsers":
            self._handle_adminUsers(body)
        elif path == "/api/adminStats":
            self._handle_adminStats(body)
        elif path == "/api/adminSeed":
            self._handle_adminSeed(body)
        else:
            self._json(404, {"code": -1, "message": "Unknown endpoint"})

    # ── 用户端 Handlers ──

    def _handle_login(self, body):
        openid = body.get("openid", f"mock_openid_{random.randint(1000, 9999)}")
        if openid not in USERS:
            USERS[openid] = {
                "_id": openid, "_openid": openid,
                "nickname": f"User_{openid[-4:]}",
                "avatar": "", "gender": 0,
                "height": 175, "weight": 70,
                "goal": "general", "unit": "kg",
                "bodyMetrics": {"height": 175, "weight": 70, "bodyFat": 15},
                "createdAt": time.time()
            }
        user = USERS[openid]
        self._json(200, {"code": 0, "openid": openid, "userInfo": user, "data": user})

    def _handle_getExercises(self, body):
        # 支持两种调用方式: {action, data:{}} 或扁平 {category, keyword, ...}
        action = body.get("action", "list")
        data = body.get("data", body)  # 扁平参数兼容

        if action == "list":
            page = data.get("page", 1)
            page_size = data.get("pageSize", 20)
            category = data.get("category")
            keyword = data.get("keyword", "")
            difficulty = data.get("difficulty")
            equipment = data.get("equipment")
            items = [e for e in EXERCISES_DB if e["status"] == "active"]
            if category:
                items = [e for e in items if e["category"] == category]
            if keyword:
                items = [e for e in items if keyword.lower() in e["name"].lower()]
            if difficulty:
                items = [e for e in items if e.get("difficulty") == difficulty]
            if equipment:
                items = [e for e in items if e.get("equipment") == equipment]
            start = (page - 1) * page_size
            self._json(200, {
                "code": 0, "data": {
                    "items": items[start:start + page_size],
                    "total": len(items), "page": page, "pageSize": page_size
                }
            })

        elif action == "detail":
            ex_id = data.get("id")
            ex = next((e for e in EXERCISES_DB if e["_id"] == ex_id), None)
            if ex:
                self._json(200, {"code": 0, "data": ex})
            else:
                self._json(200, {"code": -1, "message": "Not found"})

        elif action == "search":
            keyword = data.get("keyword", "")
            items = [e for e in EXERCISES_DB
                     if e["status"] == "active" and keyword.lower() in e["name"].lower()]
            self._json(200, {"code": 0, "data": items})

        elif action == "byCategory":
            category = data.get("category")
            items = [e for e in EXERCISES_DB
                     if e["status"] == "active" and (not category or e["category"] == category)]
            self._json(200, {"code": 0, "data": items})

        else:
            self._json(200, {"code": -1, "message": "Unknown action"})

    def _handle_getPlans(self, body):
        action = body.get("action", "list")
        if action == "list":
            goal = body.get("goal")
            page = body.get("page", 1)
            page_size = body.get("pageSize", 20)
            plans = list(PLANS_DB)
            if goal:
                plans = [p for p in plans if p.get("goal") == goal]
            start = (page - 1) * page_size
            self._json(200, {"code": 0, "data": {
                "items": plans[start:start + page_size],
                "total": len(plans), "page": page, "pageSize": page_size
            }})
        elif action == "detail":
            plan_id = body.get("planId")
            plan = next((p for p in PLANS_DB if p["_id"] == plan_id), None)
            if plan:
                self._json(200, {"code": 0, "data": plan})
            else:
                self._json(200, {"code": -1, "message": "Not found"})
        elif action == "create":
            name = body.get("name", "")
            if not name:
                self._json(200, {"code": -1, "message": "Name required"})
                return
            plan = {
                "_id": _gen_id("plan"), "name": name,
                "goal": body.get("goal", "general"),
                "frequency": body.get("frequency", 3),
                "days": body.get("days", []),
                "isActive": False, "isTemplate": False,
                "createdBy": body.get("openid", "mock_user"),
                "assignedTo": [], "createdAt": time.time()
            }
            PLANS_DB.append(plan)
            self._json(200, {"code": 0, "data": plan})
        elif action == "update":
            plan_id = body.get("planId")
            plan = next((p for p in PLANS_DB if p["_id"] == plan_id), None)
            if not plan:
                self._json(200, {"code": -1, "message": "Not found"})
                return
            for k, v in body.items():
                if k not in ("action", "planId") and v is not None:
                    plan[k] = v
            self._json(200, {"code": 0, "data": plan})
        elif action == "delete":
            plan_id = body.get("planId")
            idx = next((i for i, p in enumerate(PLANS_DB) if p["_id"] == plan_id), -1)
            if idx < 0:
                self._json(200, {"code": -1, "message": "Not found"})
                return
            PLANS_DB.pop(idx)
            self._json(200, {"code": 0, "data": {"deleted": plan_id}})
        elif action == "active":
            plan = next((p for p in PLANS_DB if p.get("isActive")), None)
            if plan:
                self._json(200, {"code": 0, "data": plan})
            else:
                self._json(200, {"code": 0, "data": None})
        else:
            self._json(200, {"code": -1, "message": "Unknown action"})

    def _handle_saveWorkout(self, body):
        action = body.get("action", "save")
        if action == "save":
            exercises = body.get("exercises", [])
            total_sets = sum(len(ex.get("sets", [])) for ex in exercises)
            total_volume = sum(
                s.get("weight", 0) * s.get("reps", 0)
                for ex in exercises for s in ex.get("sets", [])
            )
            wk = {
                "_id": _gen_id("wk"), "planId": body.get("planId"),
                "planName": body.get("planName", ""),
                "exercises": exercises, "status": "completed",
                "totalSets": total_sets, "totalVolume": total_volume,
                "startTime": time.time(), "endTime": time.time() + body.get("duration", 1800),
                "duration": body.get("duration", 0), "volume": body.get("volume", total_volume),
                "createdAt": time.time()
            }
            WORKOUTS.append(wk)
            self._json(200, {"code": 0, "data": wk})
        elif action == "start":
            exercises = body.get("exercises", [])
            wk = {
                "_id": _gen_id("wk"), "planId": body.get("planId"),
                "planName": body.get("planName", ""),
                "exercises": exercises, "status": "in_progress",
                "startTime": time.time(), "endTime": None,
                "duration": 0, "totalSets": 0, "totalVolume": 0,
                "createdAt": time.time()
            }
            WORKOUTS.append(wk)
            self._json(200, {"code": 0, "data": wk})
        elif action == "updateSet":
            wid = body.get("workoutId")
            wk = next((w for w in WORKOUTS if w["_id"] == wid), None)
            if not wk:
                self._json(200, {"code": -1, "message": "Not found"})
                return
            ex_idx = body.get("exerciseIndex", 0)
            set_idx = body.get("setIndex", 0)
            set_data = body.get("setData", {})
            if ex_idx < len(wk["exercises"]) and set_idx < len(wk["exercises"][ex_idx].get("sets", [])):
                wk["exercises"][ex_idx]["sets"][set_idx].update(set_data)
            self._json(200, {"code": 0, "data": wk})
        elif action == "complete":
            wid = body.get("workoutId")
            wk = next((w for w in WORKOUTS if w["_id"] == wid), None)
            if not wk:
                self._json(200, {"code": -1, "message": "Not found"})
                return
            wk["status"] = "completed"
            wk["endTime"] = time.time()
            wk["duration"] = body.get("duration", 0)
            # 更新PR
            for ex in wk.get("exercises", []):
                ex_id = ex.get("exerciseId", "")
                for s in ex.get("sets", []):
                    w, r = s.get("weight", 0), s.get("reps", 0)
                    if w > 0 and r > 0:
                        openid = "mock_user"
                        if openid not in PERSONAL_RECORDS:
                            PERSONAL_RECORDS[openid] = {}
                        cur = PERSONAL_RECORDS[openid].get(ex_id, {"weight": 0, "reps": 0, "volume": 0})
                        if w > cur["weight"]:
                            cur["weight"] = w
                        if r > cur["reps"]:
                            cur["reps"] = r
                        vol = w * r
                        if vol > cur["volume"]:
                            cur["volume"] = vol
                        cur["date"] = time.time()
                        PERSONAL_RECORDS[openid][ex_id] = cur
            self._json(200, {"code": 0, "data": wk})
        elif action == "history":
            page = body.get("page", 1)
            page_size = body.get("pageSize", 20)
            status = body.get("status")
            items = list(WORKOUTS)
            if status:
                items = [w for w in items if w.get("status") == status]
            items.reverse()
            start = (page - 1) * page_size
            self._json(200, {"code": 0, "data": {
                "items": items[start:start + page_size],
                "total": len(items), "page": page, "pageSize": page_size
            }})
        elif action == "detail":
            wid = body.get("workoutId")
            wk = next((w for w in WORKOUTS if w["_id"] == wid), None)
            if wk:
                self._json(200, {"code": 0, "data": wk})
            else:
                self._json(200, {"code": -1, "message": "Not found"})
        elif action == "updateProfile":
            profile = body.get("profile", {})
            nickname = profile.get("nickname", "")
            self._json(200, {"code": 0, "data": {"nickname": nickname, "updated": True}})
        elif action == "personalRecords":
            self._json(200, {"code": 0, "data": PERSONAL_RECORDS.get("mock_user", {})})
        else:
            self._json(200, {"code": -1, "message": "Unknown action"})

    def _handle_planTemplates(self, body):
        templates = [p for p in PLANS_DB if p.get("isTemplate")]
        if not templates:
            templates = [
                {"_id": "tpl_001", "name": "推拉腿分化", "goal": "hypertrophy", "frequency": 6, "isTemplate": True},
                {"_id": "tpl_002", "name": "上下肢分化", "goal": "strength", "frequency": 4, "isTemplate": True},
                {"_id": "tpl_003", "name": "全身训练", "goal": "general", "frequency": 3, "isTemplate": True},
                {"_id": "tpl_004", "name": "减脂循环", "goal": "fat_loss", "frequency": 5, "isTemplate": True},
            ]
        self._json(200, {"code": 0, "data": {"items": templates, "total": len(templates)}})

    def _handle_seedExercises(self, body):
        action = body.get("action", "init")
        if action == "init":
            self._json(200, {"code": 0, "data": {"initialized": True, "count": len(SAMPLE_EXERCISES)}})
        elif action == "status":
            active = [e for e in EXERCISES_DB if e["status"] == "active"]
            self._json(200, {"code": 0, "data": {"total": len(EXERCISES_DB), "active": len(active)}})
        else:
            self._json(200, {"code": -1, "message": "Unknown action"})

    # ── 管理端 Handlers ──

    def _handle_adminAuth(self, body):
        action = body.get("action", "")
        if action == "login":
            username = body.get("username", "")
            password = body.get("password", "")
            if not username or not password:
                self._json(200, {"code": -1, "message": "Credentials required"})
                return
            pw_hash = hashlib.sha256(password.encode()).hexdigest()
            admin = next((a for a in ADMINS.values()
                          if a["username"] == username and a["password"] == pw_hash), None)
            if not admin:
                self._json(200, {"code": -1, "message": "Invalid credentials"})
                return
            token = _make_token(admin["_id"])
            self._json(200, {"code": 0, "data": {"token": token, "admin": admin}})
        elif action == "verify":
            token = body.get("token", "")
            admin_id = _verify_token(token)
            if admin_id and admin_id in ADMINS:
                self._json(200, {"code": 0, "data": {"valid": True, "admin": ADMINS[admin_id]}})
            else:
                self._json(200, {"code": -1, "message": "Invalid token"})
        elif action == "changePassword":
            token = body.get("token", "")
            admin_id = _verify_token(token)
            if not admin_id:
                self._json(200, {"code": -1, "message": "Auth required"})
                return
            old_pw = body.get("oldPassword", "")
            new_pw = body.get("newPassword", "")
            if len(new_pw) < 6:
                self._json(200, {"code": -1, "message": "Password too short"})
                return
            admin = ADMINS[admin_id]
            if admin["password"] != hashlib.sha256(old_pw.encode()).hexdigest():
                self._json(200, {"code": -1, "message": "Wrong old password"})
                return
            admin["password"] = hashlib.sha256(new_pw.encode()).hexdigest()
            self._json(200, {"code": 0, "data": {"changed": True}})
        elif action == "createAdmin":
            token = body.get("token", "")
            admin_id = _verify_token(token)
            if not admin_id or ADMINS.get(admin_id, {}).get("role") != "super_admin":
                self._json(200, {"code": -1, "message": "Auth required or not super_admin"})
                return
            username = body.get("username", "")
            password = body.get("password", "")
            role = body.get("role", "editor")
            if not username or len(password) < 6:
                self._json(200, {"code": -1, "message": "Invalid username or password too short"})
                return
            if any(a["username"] == username for a in ADMINS.values()):
                self._json(200, {"code": -1, "message": "Username exists"})
                return
            new_admin = {
                "_id": _gen_id("admin"), "username": username,
                "password": hashlib.sha256(password.encode()).hexdigest(),
                "role": role, "createdAt": time.time()
            }
            ADMINS[new_admin["_id"]] = new_admin
            self._json(200, {"code": 0, "data": new_admin})
        else:
            self._json(200, {"code": -1, "message": "Unknown action"})

    def _handle_adminExercises(self, body):
        action = body.get("action", "list")
        token = body.get("token", "")
        if not _verify_token(token):
            self._json(200, {"code": -1, "message": "Auth required"})
            return

        if action == "list":
            category = body.get("category")
            keyword = body.get("keyword", "")
            status = body.get("status")
            items = list(EXERCISES_DB)
            if category:
                items = [e for e in items if e["category"] == category]
            if keyword:
                items = [e for e in items if keyword.lower() in e["name"].lower()]
            if status:
                items = [e for e in items if e.get("status") == status]
            self._json(200, {"code": 0, "data": {"items": items, "total": len(items)}})
        elif action == "detail":
            ex_id = body.get("exerciseId")
            ex = next((e for e in EXERCISES_DB if e["_id"] == ex_id), None)
            if ex:
                self._json(200, {"code": 0, "data": ex})
            else:
                self._json(200, {"code": -1, "message": "Not found"})
        elif action == "create":
            name = body.get("name", "")
            category = body.get("category", "")
            if not name or not category:
                self._json(200, {"code": -1, "message": "Name and category required"})
                return
            ex = {
                "_id": _gen_id("ex"), "name": name,
                "category": category, "difficulty": body.get("difficulty", "beginner"),
                "equipment": body.get("equipment", ""), "muscleGroups": body.get("muscleGroups", []),
                "status": "active", "createdBy": "admin", "createdAt": time.time()
            }
            EXERCISES_DB.append(ex)
            self._json(200, {"code": 0, "data": ex})
        elif action == "update":
            ex_id = body.get("exerciseId")
            ex = next((e for e in EXERCISES_DB if e["_id"] == ex_id), None)
            if not ex:
                self._json(200, {"code": -1, "message": "Not found"})
                return
            for k, v in body.items():
                if k not in ("action", "token", "exerciseId") and v is not None:
                    ex[k] = v
            self._json(200, {"code": 0, "data": ex})
        elif action == "delete":
            ex_id = body.get("exerciseId")
            idx = next((i for i, e in enumerate(EXERCISES_DB) if e["_id"] == ex_id), -1)
            if idx < 0:
                self._json(200, {"code": -1, "message": "Not found"})
                return
            EXERCISES_DB.pop(idx)
            self._json(200, {"code": 0, "data": {"deleted": ex_id}})
        elif action == "batchStatus":
            ids = body.get("exerciseIds", [])
            new_status = body.get("status", "active")
            if not ids:
                self._json(200, {"code": -1, "message": "IDs required"})
                return
            count = 0
            for e in EXERCISES_DB:
                if e["_id"] in ids:
                    e["status"] = new_status
                    count += 1
            self._json(200, {"code": 0, "data": {"updated": count}})
        elif action == "stats":
            active = [e for e in EXERCISES_DB if e["status"] == "active"]
            by_cat = {}
            for e in EXERCISES_DB:
                by_cat[e["category"]] = by_cat.get(e["category"], 0) + 1
            by_diff = {}
            for e in EXERCISES_DB:
                by_diff[e.get("difficulty", "unknown")] = by_diff.get(e.get("difficulty", "unknown"), 0) + 1
            self._json(200, {"code": 0, "data": {
                "total": len(EXERCISES_DB), "active": len(active),
                "byCategory": by_cat, "byDifficulty": by_diff
            }})
        else:
            self._json(200, {"code": -1, "message": "Unknown action"})

    def _handle_adminPlans(self, body):
        action = body.get("action", "list")
        token = body.get("token", "")
        if not _verify_token(token):
            self._json(200, {"code": -1, "message": "Auth required"})
            return

        if action == "list":
            is_template = body.get("isTemplate")
            goal = body.get("goal")
            items = list(PLANS_DB)
            if is_template is not None:
                items = [p for p in items if p.get("isTemplate") == is_template]
            if goal:
                items = [p for p in items if p.get("goal") == goal]
            self._json(200, {"code": 0, "data": {"items": items, "total": len(items)}})
        elif action == "detail":
            plan_id = body.get("planId")
            plan = next((p for p in PLANS_DB if p["_id"] == plan_id), None)
            if plan:
                self._json(200, {"code": 0, "data": plan})
            else:
                self._json(200, {"code": -1, "message": "Not found"})
        elif action == "create":
            name = body.get("name", "")
            if not name:
                self._json(200, {"code": -1, "message": "Name required"})
                return
            plan = {
                "_id": _gen_id("plan"), "name": name,
                "goal": body.get("goal", "general"),
                "frequency": body.get("frequency", 3),
                "days": body.get("days", []),
                "isActive": False, "isTemplate": body.get("isTemplate", False),
                "createdBy": "admin", "assignedTo": [], "createdAt": time.time()
            }
            PLANS_DB.append(plan)
            self._json(200, {"code": 0, "data": plan})
        elif action == "update":
            plan_id = body.get("planId")
            plan = next((p for p in PLANS_DB if p["_id"] == plan_id), None)
            if not plan:
                self._json(200, {"code": -1, "message": "Not found"})
                return
            for k, v in body.items():
                if k not in ("action", "token", "planId") and v is not None:
                    plan[k] = v
            self._json(200, {"code": 0, "data": plan})
        elif action == "delete":
            plan_id = body.get("planId")
            idx = next((i for i, p in enumerate(PLANS_DB) if p["_id"] == plan_id), -1)
            if idx < 0:
                self._json(200, {"code": -1, "message": "Not found"})
                return
            PLANS_DB.pop(idx)
            self._json(200, {"code": 0, "data": {"deleted": plan_id}})
        elif action == "setTemplate":
            plan_id = body.get("planId")
            plan = next((p for p in PLANS_DB if p["_id"] == plan_id), None)
            if not plan:
                self._json(200, {"code": -1, "message": "Not found"})
                return
            plan["isTemplate"] = body.get("isTemplate", True)
            self._json(200, {"code": 0, "data": plan})
        elif action == "assign":
            plan_id = body.get("planId")
            user_ids = body.get("userIds", [])
            if not user_ids:
                self._json(200, {"code": -1, "message": "User IDs required"})
                return
            plan = next((p for p in PLANS_DB if p["_id"] == plan_id), None)
            if not plan:
                self._json(200, {"code": -1, "message": "Plan not found"})
                return
            assigned = list(set(plan.get("assignedTo", []) + user_ids))
            plan["assignedTo"] = assigned
            self._json(200, {"code": 0, "data": {"assignedTo": assigned}})
        elif action == "stats":
            templates = [p for p in PLANS_DB if p.get("isTemplate")]
            active = [p for p in PLANS_DB if p.get("isActive")]
            by_goal = {}
            for p in PLANS_DB:
                by_goal[p.get("goal", "unknown")] = by_goal.get(p.get("goal", "unknown"), 0) + 1
            self._json(200, {"code": 0, "data": {
                "total": len(PLANS_DB), "templates": len(templates),
                "active": len(active), "byGoal": by_goal
            }})
        else:
            self._json(200, {"code": -1, "message": "Unknown action"})

    def _handle_adminUsers(self, body):
        action = body.get("action", "list")
        token = body.get("token", "")
        if not _verify_token(token):
            self._json(200, {"code": -1, "message": "Auth required"})
            return

        if action == "list":
            keyword = body.get("keyword", "")
            items = list(USERS.values())
            if keyword:
                items = [u for u in items if keyword.lower() in u.get("nickname", "").lower()]
            self._json(200, {"code": 0, "data": {"items": items, "total": len(items)}})
        elif action == "detail":
            user_id = body.get("userId")
            user = USERS.get(user_id)
            if not user:
                self._json(200, {"code": -1, "message": "Not found"})
                return
            user_workouts = [w for w in WORKOUTS if w.get("userId") == user_id]
            self._json(200, {"code": 0, "data": {
                **user, "workoutSummary": {
                    "totalWorkouts": len(user_workouts),
                    "totalDuration": sum(w.get("duration", 0) for w in user_workouts),
                    "totalVolume": sum(w.get("totalVolume", 0) for w in user_workouts)
                }
            }})
        elif action == "update":
            user_id = body.get("userId")
            user = USERS.get(user_id)
            if not user:
                self._json(200, {"code": -1, "message": "Not found"})
                return
            for k, v in body.items():
                if k not in ("action", "token", "userId") and v is not None:
                    if k == "bodyMetrics":
                        user.setdefault("bodyMetrics", {}).update(v)
                    else:
                        user[k] = v
            self._json(200, {"code": 0, "data": user})
        elif action == "delete":
            user_id = body.get("userId")
            if user_id not in USERS:
                self._json(200, {"code": -1, "message": "Not found"})
                return
            del USERS[user_id]
            self._json(200, {"code": 0, "data": {"deleted": user_id}})
        elif action == "workoutHistory":
            user_id = body.get("userId")
            items = [w for w in WORKOUTS if w.get("userId") == user_id]
            self._json(200, {"code": 0, "data": {"items": items, "total": len(items)}})
        elif action == "bodyMetrics":
            user_id = body.get("userId")
            history = BODY_METRICS_DB.get(user_id, [{"date": "2025-05-20", "weight": 70, "bodyFat": 15}])
            self._json(200, {"code": 0, "data": {"current": history[0] if history else {}, "history": history}})
        elif action == "personalRecords":
            user_id = body.get("userId")
            self._json(200, {"code": 0, "data": PERSONAL_RECORDS.get(user_id, {})})
        else:
            self._json(200, {"code": -1, "message": "Unknown action"})

    def _handle_adminStats(self, body):
        action = body.get("action", "overview")
        token = body.get("token", "")
        if not _verify_token(token):
            self._json(200, {"code": -1, "message": "Auth required"})
            return

        if action == "overview":
            self._json(200, {"code": 0, "data": {
                "totalUsers": len(USERS), "totalWorkouts": len(WORKOUTS),
                "totalExercises": len(EXERCISES_DB),
                "totalPlans": len(PLANS_DB),
                "completedWorkouts": len([w for w in WORKOUTS if w.get("status") == "completed"])
            }})
        elif action == "workoutTrends":
            days = body.get("days", 7)
            trends = [{"date": f"2025-05-{22 - i:02d}", "count": random.randint(0, 5)} for i in range(days)]
            self._json(200, {"code": 0, "data": {"trends": trends}})
        elif action == "userGrowth":
            days = body.get("days", 7)
            growth = [{"date": f"2025-05-{22 - i:02d}", "newUsers": random.randint(0, 3),
                       "totalUsers": len(USERS) + i} for i in range(days)]
            self._json(200, {"code": 0, "data": {"growth": growth}})
        elif action == "exerciseUsage":
            self._json(200, {"code": 0, "data": {"usage": [], "total": 0}})
        elif action == "popularCategories":
            self._json(200, {"code": 0, "data": {"categories": []}})
        elif action == "export":
            export_type = body.get("type", "")
            if export_type not in ("users", "workouts", "exercises"):
                self._json(200, {"code": -1, "message": "Invalid export type"})
                return
            data_map = {"users": list(USERS.values()), "workouts": WORKOUTS, "exercises": EXERCISES_DB}
            data = data_map[export_type]
            self._json(200, {"code": 0, "data": {"type": export_type, "data": data, "count": len(data)}})
        else:
            self._json(200, {"code": -1, "message": "Unknown action"})

    def _handle_adminSeed(self, body):
        action = body.get("action", "")
        token = body.get("token", "")
        if not _verify_token(token):
            self._json(200, {"code": -1, "message": "Auth required"})
            return

        if action == "import":
            count = body.get("count", 10)
            SEED_STATS["imported"] = SEED_STATS.get("imported", 0) + count
            SEED_STATS["lastImport"] = time.time()
            self._json(200, {"code": 0, "data": {"imported": count}})
        elif action == "clear":
            removed = SEED_STATS.get("imported", 0)
            SEED_STATS["imported"] = 0
            self._json(200, {"code": 0, "data": {"removed": removed}})
        elif action == "stats":
            self._json(200, {"code": 0, "data": {
                "totalExercises": len(EXERCISES_DB),
                "seedExercises": SEED_STATS.get("imported", 0),
                "customExercises": len(EXERCISES_DB) - SEED_STATS.get("imported", 0)
            }})
        else:
            self._json(200, {"code": -1, "message": "Unknown action"})

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
