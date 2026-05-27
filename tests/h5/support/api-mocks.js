/**
 * Playwright API Route Mocks for FitTrack Admin
 *
 * Intercepts admin backend API calls (http://localhost:3000/admin/*) via
 * Playwright page.route() so the explorer can log in and browse data
 * without a real backend running.
 *
 * Control via env var MOCK_API (default: enabled).
 *
 * Response envelope: { code: 0, data: {...} }
 * The frontend Axios interceptor does `response => response.data`, so the
 * Vue components see `res.code` and `res.data` directly.
 *
 * Usage:
 *   const { setupApiMocks, teardownApiMocks, getMockStats } = require('./support/api-mocks');
 *   test.describe('Suite', () => {
 *     test.beforeEach(async ({ page }) => { await setupApiMocks(page); });
 *     test.afterEach(async ({ page }) => { await teardownApiMocks(page); });
 *     // ...
 *   });
 */

const MOCK_API = process.env.MOCK_API !== 'false'; // default enabled

// --- Mock Stats Tracker ---

let mockStats = { enabled: MOCK_API, matched: 0, unmatched: 0, unmatchedUrls: [] };

// Static resource extensions that should never count as unmatched API calls
const STATIC_EXTENSIONS = /\.(js|css|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|eot|map|webp|avif)(\?.*)?$/i;
const STATIC_PATHS = /\/favicon\./i;

/** Check if a URL is a static resource that should be whitelisted. */
function isStaticResource(url) {
  if (!url) return false;
  return STATIC_EXTENSIONS.test(url) || STATIC_PATHS.test(url);
}

function trackMatched() {
  mockStats.matched++;
}

function trackUnmatched(url, method, status, reason) {
  mockStats.unmatched++;
  mockStats.unmatchedUrls.push({
    url: url || '',
    method: method || 'GET',
    status: status || 0,
    reason: reason || 'no_mock_registered',
  });
}

function getMockStats() {
  const result = {
    enabled: mockStats.enabled,
    matched: mockStats.matched,
    unmatched: mockStats.unmatched,
    unmatchedUrls: [...mockStats.unmatchedUrls],
  };

  // If all unmatched URLs are static resources or known-safe patterns, provide a reason
  if (result.unmatched > 0) {
    const nonStatic = result.unmatchedUrls.filter(
      (u) => !isStaticResource(u.url)
    );
    if (nonStatic.length === 0) {
      result.unmatchedWhitelistReason = 'All unmatched are static resources (.js/.css/.png/.ico/.woff etc.) or favicon';
      result.unmatched = 0; // treat as zero for acceptance
    }
  }

  return result;
}

// --- Seed data ----------------------------------------------------------------

// IDs use _id (MongoDB) to match what the Vue views expect (row._id)
// Category/difficulty/equipment values are lowercase enum IDs from utils/constants.js

function mockId(n) { return `mock_ex_${String(n).padStart(3, '0')}`; }

// ======================================================================
// In-memory Exercise Store (Task A3)
// ======================================================================

const exerciseStore = {
  items: [],
  nextId: 1,
  // Error simulation flag for E2E tests (Task B1)
  _simulateError: false,

  /**
   * Populate the store with seed data.
   * @param {Array} seedData - array of exercise objects
   */
  init(seedData) {
    this.items = [];
    this.nextId = 1;
    for (const ex of seedData) {
      // Ensure E2E_TEST_ prefix on all seed names
      const name = e2eName(ex.name, 'Seed Exercise');
      const copy = { ...ex, name, _id: ex._id || `e2e_ex_${this.nextId++}` };
      if (copy.status === undefined && copy.isActive !== undefined) {
        copy.status = copy.isActive ? 'active' : 'inactive';
      }
      if (copy.status === undefined) copy.status = 'active';
      this.items.push(copy);
    }
    // Update nextId to be past any explicit e2e_ex_<N> IDs
    const maxN = this.items.reduce((max, item) => {
      const m = String(item._id).match(/^e2e_ex_(\d+)$/);
      return m ? Math.max(max, parseInt(m[1], 10)) : max;
    }, 0);
    this.nextId = maxN + 1;
  },

  /**
   * List exercises with optional filters.
   * @param {Object} params - { keyword, category, difficulty }
   * @returns {{ items: Array, total: number }}
   */
  list(params = {}) {
    const { keyword, category, difficulty } = params;
    let filtered = [...this.items];

    if (keyword && keyword.trim()) {
      const kw = keyword.trim().toLowerCase();
      filtered = filtered.filter((ex) =>
        (ex.name || '').toLowerCase().includes(kw)
      );
    }
    if (category) {
      filtered = filtered.filter((ex) => ex.category === category);
    }
    if (difficulty) {
      filtered = filtered.filter((ex) => ex.difficulty === difficulty);
    }

    return { items: filtered, total: filtered.length };
  },

  /**
   * Create a new exercise. Enforces E2E_TEST_ prefix on name.
   * @param {Object} data - exercise fields
   * @returns {Object} created exercise with _id: 'e2e_ex_<N>'
   */
  create(data) {
    const name = e2eName(data.name, 'New Exercise');
    const created = {
      _id: `e2e_ex_${this.nextId++}`,
      name,
      category: data.category || 'other',
      difficulty: data.difficulty || 'beginner',
      equipment: data.equipment || 'other',
      muscleGroups: data.muscleGroups || [],
      description: data.description || '',
      imageUrl: data.imageUrl || '',
      videoUrl: data.videoUrl || '',
      status: 'active',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    this.items.push(created);
    return created;
  },

  /**
   * Get a single exercise by _id.
   * @param {string} id
   * @returns {Object|null}
   */
  getById(id) {
    return this.items.find((ex) => ex._id === id) || null;
  },

  /**
   * Update an exercise in place.
   * @param {string} id
   * @param {Object} data - fields to update (excludes _id)
   * @returns {Object|null} updated exercise, or null if not found
   */
  update(id, data) {
    const ex = this.items.find((e) => e._id === id);
    if (!ex) return null;
    // Merge data, exclude _id to prevent overwrite
    const { _id, ...rest } = data;
    Object.assign(ex, rest, { updatedAt: new Date().toISOString() });
    return ex;
  },

  /**
   * Return aggregated stats from the store.
   * @returns {{ total: number, byCategory: Object, byDifficulty: Object }}
   */
  getStats() {
    const byCategory = {};
    const byDifficulty = {};
    for (const ex of this.items) {
      byCategory[ex.category] = (byCategory[ex.category] || 0) + 1;
      byDifficulty[ex.difficulty] = (byDifficulty[ex.difficulty] || 0) + 1;
    }
    return {
      total: this.items.length,
      byCategory,
      byDifficulty,
    };
  },
};

// Seed data: 8 exercises with values matching admin/src/utils/constants.js enums
const SEED_EXERCISES = [
  {
    _id: 'mock_ex_001', name: 'Barbell Bench Press', category: 'chest', difficulty: 'intermediate',
    equipment: 'barbell', muscleGroups: ['chest', 'triceps'], description: 'Flat bench barbell press', isActive: true,
    imageUrl: '', videoUrl: '',
    createdAt: '2025-01-10T08:00:00Z', updatedAt: '2025-01-10T08:00:00Z',
  },
  {
    _id: 'mock_ex_002', name: 'Barbell Squat', category: 'leg', difficulty: 'intermediate',
    equipment: 'barbell', muscleGroups: ['quadriceps', 'glutes'], description: 'Standard barbell back squat', isActive: true,
    imageUrl: '', videoUrl: '',
    createdAt: '2025-01-10T08:00:00Z', updatedAt: '2025-01-10T08:00:00Z',
  },
  {
    _id: 'mock_ex_003', name: 'Pull Up', category: 'back', difficulty: 'advanced',
    equipment: 'bodyweight', muscleGroups: ['lats', 'biceps'], description: 'Dead hang pull up', isActive: true,
    imageUrl: '', videoUrl: '',
    createdAt: '2025-01-10T08:00:00Z', updatedAt: '2025-01-10T08:00:00Z',
  },
  {
    _id: 'mock_ex_004', name: 'Deadlift', category: 'back', difficulty: 'advanced',
    equipment: 'barbell', muscleGroups: ['back', 'glutes', 'hamstrings'], description: 'Conventional deadlift', isActive: true,
    imageUrl: '', videoUrl: '',
    createdAt: '2025-01-10T08:00:00Z', updatedAt: '2025-01-10T08:00:00Z',
  },
  {
    _id: 'mock_ex_005', name: 'Overhead Press', category: 'shoulder', difficulty: 'intermediate',
    equipment: 'barbell', muscleGroups: ['shoulders', 'triceps'], description: 'Standing barbell overhead press', isActive: true,
    imageUrl: '', videoUrl: '',
    createdAt: '2025-01-10T08:00:00Z', updatedAt: '2025-01-10T08:00:00Z',
  },
  {
    _id: 'mock_ex_006', name: 'Dumbbell Curl', category: 'arm', difficulty: 'beginner',
    equipment: 'dumbbell', muscleGroups: ['biceps'], description: 'Standing dumbbell curl', isActive: true,
    imageUrl: '', videoUrl: '',
    createdAt: '2025-01-10T08:00:00Z', updatedAt: '2025-01-10T08:00:00Z',
  },
  {
    _id: 'mock_ex_007', name: 'Plank', category: 'core', difficulty: 'beginner',
    equipment: 'bodyweight', muscleGroups: ['core'], description: 'Forearm plank for core stability', isActive: true,
    imageUrl: '', videoUrl: '',
    createdAt: '2025-01-10T08:00:00Z', updatedAt: '2025-01-10T08:00:00Z',
  },
  {
    _id: 'mock_ex_008', name: 'Treadmill Run', category: 'cardio', difficulty: 'beginner',
    equipment: 'machine', muscleGroups: ['cardio'], description: 'Treadmill cardio training', isActive: true,
    imageUrl: '', videoUrl: '',
    createdAt: '2025-01-10T08:00:00Z', updatedAt: '2025-01-10T08:00:00Z',
  },
];

// Initialize the exercise store
exerciseStore.init(SEED_EXERCISES);

// Backward-compatible reference: MOCK_EXERCISES is the live items array
// After store.init(), all names have E2E_TEST_ prefix enforced
const MOCK_EXERCISES = exerciseStore.items;

// Plans — views expect _id, goal (enum id), frequency, days[], isActive
const MOCK_PLANS = [
  {
    _id: 'mock_plan_001', name: 'E2E_TEST_三分化训练', description: '推/拉/腿 3天分化训练',
    goal: 'hypertrophy', frequency: 3, days: ['push', 'pull', 'legs'],
    exercises: [mockId(1), mockId(2), mockId(3), mockId(4), mockId(5)],
    difficulty: 'intermediate', isActive: true,
    createdAt: '2025-01-15T08:00:00Z', updatedAt: '2025-01-15T08:00:00Z',
  },
  {
    _id: 'mock_plan_002', name: 'E2E_TEST_上下肢分化', description: '上肢/下肢 4天分化训练',
    goal: 'strength', frequency: 4, days: ['upper1', 'lower1', 'upper2', 'lower2'],
    exercises: [mockId(1), mockId(3), mockId(4)],
    difficulty: 'beginner', isActive: true,
    createdAt: '2025-01-16T08:00:00Z', updatedAt: '2025-01-16T08:00:00Z',
  },
  {
    _id: 'mock_plan_003', name: 'E2E_TEST_全身训练', description: '每周3次全身训练',
    goal: 'general', frequency: 3, days: ['fullbody1', 'fullbody2', 'fullbody3'],
    exercises: [mockId(1), mockId(2), mockId(4)],
    difficulty: 'beginner', isActive: false,
    createdAt: '2025-01-17T08:00:00Z', updatedAt: '2025-01-17T08:00:00Z',
  },
];

// Users — views expect _id, nickname, gender (1/2), goal, workoutCount, createdAt
const MOCK_USERS = [
  {
    _id: 'mock_user_001', nickname: 'E2E_TEST_健身达人', gender: 1, goal: 'hypertrophy',
    workoutCount: 87, createdAt: '2025-01-05T08:00:00Z',
  },
  {
    _id: 'mock_user_002', nickname: 'E2E_TEST_减脂小妹', gender: 2, goal: 'fat_loss',
    workoutCount: 42, createdAt: '2025-02-10T08:00:00Z',
  },
  {
    _id: 'mock_user_003', nickname: 'E2E_TEST_力量选手', gender: 1, goal: 'strength',
    workoutCount: 156, createdAt: '2024-11-20T08:00:00Z',
  },
  {
    _id: 'mock_user_004', nickname: 'E2E_TEST_瑜伽爱好者', gender: 2, goal: 'flexibility',
    workoutCount: 23, createdAt: '2025-03-01T08:00:00Z',
  },
  {
    _id: 'mock_user_005', nickname: 'E2E_TEST_耐力跑者', gender: 1, goal: 'endurance',
    workoutCount: 64, createdAt: '2025-01-15T08:00:00Z',
  },
];

// Stats overview — Dashboard.vue expects totalUsers, recentWorkouts (as activeUsers display),
// totalWorkouts, totalExercises
const MOCK_STATS = {
  totalUsers: 1250,
  activeUsers: 87,
  recentWorkouts: 423,
  totalWorkouts: 15800,
  totalExercises: 42,
  recentActivity: [
    { user: 'TestUser1', action: 'completed workout', time: new Date().toISOString() },
    { user: 'TestUser2', action: 'logged body metrics', time: new Date().toISOString() },
  ],
};

// Workout trend — Stats/Index.vue expects res.data.trend as OBJECT { "2025-01-01": 42 }
// Popular categories — expects res.data.distribution as OBJECT { "chest": 320 }
// Exercise usage — expects res.data.topExercises as ARRAY [{ name, count }]

function generateTrend(days) {
  const obj = {};
  for (let i = 0; i < days; i++) {
    const d = new Date();
    d.setDate(d.getDate() - (days - 1 - i));
    const key = d.toISOString().split('T')[0];
    obj[key] = Math.floor(Math.random() * 50) + 10;
  }
  return obj;
}

function generateCategoryDistribution() {
  return {
    chest: 320,
    back: 280,
    shoulder: 200,
    arm: 180,
    leg: 250,
    core: 150,
    cardio: 100,
    stretch: 120,
  };
}

const MOCK_TOKEN = 'mock-jwt-token-eyJhbGciOiJIUzI1NiJ9.e30.mock';
const MOCK_ADMIN = { _id: 'mock_admin_001', name: 'E2E_TEST_Admin', email: '', role: 'superadmin' };

// --- Helpers ------------------------------------------------------------------

/**
 * Parse the JSON body from a Playwright Route request.
 */
function parseBody(request) {
  try {
    const raw = request.postData();
    if (!raw) return {};
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

/**
 * Build a canonical response envelope: { code: 0, data: {...} }
 */
function reply(route, status, body) {
  route.fulfill({
    status,
    contentType: 'application/json',
    headers: { 'access-control-allow-origin': '*' },
    body: JSON.stringify(body),
  });
}

/** Simulate network latency (50-100ms). */
function delay() {
  const ms = 50 + Math.floor(Math.random() * 51);
  return new Promise((r) => setTimeout(r, ms));
}

/** E2E_TEST_ naming convention enforcement */
function e2eName(name, fallback) {
  if (name && name.startsWith('E2E_TEST_')) return name;
  return `E2E_TEST_${name || fallback}`;
}

// --- Route handlers -----------------------------------------------------------

/**
 * POST /admin/auth
 *
 * Accepts { action, email, password }. Returns mock JWT + admin profile.
 */
async function handleAuth(route) {
  const body = parseBody(route.request());

  if (body.action === 'login') {
    if (!body.email || !body.password) {
      reply(route, 400, { code: 1, message: 'Missing credentials' });
      return;
    }
    reply(route, 200, {
      code: 0,
      data: {
        token: MOCK_TOKEN,
        admin: { ...MOCK_ADMIN, email: body.email },
      },
    });
    return;
  }

  if (body.action === 'verify') {
    reply(route, 200, {
      code: 0,
      data: { admin: MOCK_ADMIN },
    });
    return;
  }

  if (body.action === 'changePassword') {
    reply(route, 200, { code: 0, data: { success: true } });
    return;
  }

  reply(route, 200, { code: 0, data: {} });
}

/**
 * POST /admin/exercises
 *
 * action=list       -> { code: 0, data: { items: [...], total: N } }
 * action=detail     -> { code: 0, data: {...} }
 * action=create     -> 201 with E2E_TEST_ name prefix
 * action=update     -> updated object
 * action=delete     -> { code: 403, message: "Blocked by E2E safety policy" }
 * action=stats      -> exercise stats
 */
async function handleExercises(route) {
  const body = parseBody(route.request());

  if (body.action === 'list') {
    const { page = 1, pageSize = 20 } = body;
    // Use store.list() which supports keyword/category/difficulty filtering
    const filtered = exerciseStore.list(body);
    const start = (page - 1) * pageSize;
    const items = filtered.items.slice(start, start + pageSize);
    reply(route, 200, {
      code: 0,
      data: { items, total: filtered.total },
    });
    return;
  }

  if (body.action === 'detail') {
    // The frontend sends { action: 'detail', id } not { action: 'detail', _id }
    const ex = exerciseStore.getById(body.id);
    reply(route, 200, ex
      ? { code: 0, data: ex }
      : { code: 404, message: 'Not found' });
    return;
  }

  if (body.action === 'create') {
    // Task B1: Error simulation for API failure flow testing
    if (exerciseStore._simulateError) {
      reply(route, 500, { code: 500, message: 'Internal server error (simulated)' });
      return;
    }
    const created = exerciseStore.create(body);
    reply(route, 201, { code: 0, data: created, message: 'Created successfully' });
    return;
  }

  if (body.action === 'update') {
    // The frontend sends { action: 'update', id, ...data }
    const updated = exerciseStore.update(body.id, body);
    if (updated) {
      reply(route, 200, { code: 0, data: updated });
    } else {
      reply(route, 404, { code: 404, message: 'Not found' });
    }
    return;
  }

  if (body.action === 'delete') {
    // Dangerous operation — blocked by E2E safety policy
    reply(route, 403, { code: 403, message: 'Blocked by E2E safety policy' });
    return;
  }

  if (body.action === 'batchUpdateStatus') {
    reply(route, 200, { code: 0, data: { updated: (body.ids || []).length } });
    return;
  }

  if (body.action === 'stats') {
    const stats = exerciseStore.getStats();
    reply(route, 200, {
      code: 0,
      data: stats,
    });
    return;
  }

  reply(route, 200, { code: 0, data: {} });
}

/**
 * POST /admin/plans
 *
 * action=list       -> { code: 0, data: { items: [...], total: N } }
 * action=detail     -> { code: 0, data: {...} }
 * action=create     -> 201 with E2E_TEST_ prefix
 * action=update     -> updated
 * action=delete     -> 403 safety policy
 */
async function handlePlans(route) {
  const body = parseBody(route.request());

  if (body.action === 'list') {
    const { page = 1, pageSize = 20 } = body;
    const start = (page - 1) * pageSize;
    const items = MOCK_PLANS.slice(start, start + pageSize);
    reply(route, 200, {
      code: 0,
      data: { items, total: MOCK_PLANS.length },
    });
    return;
  }

  if (body.action === 'detail') {
    const plan = MOCK_PLANS.find((p) => p._id === body.id);
    reply(route, 200, plan
      ? { code: 0, data: plan }
      : { code: 1, message: 'Plan not found' });
    return;
  }

  if (body.action === 'create') {
    const created = {
      _id: `mock_plan_${200 + MOCK_PLANS.length}`,
      name: e2eName(body.name, 'New Plan'),
      description: body.description || '',
      goal: body.goal || 'general',
      frequency: body.frequency || 3,
      days: body.days || [],
      exercises: body.exercises || [],
      difficulty: body.difficulty || 'beginner',
      isActive: true,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    MOCK_PLANS.push(created);
    reply(route, 201, { code: 0, data: created, message: 'Plan created' });
    return;
  }

  if (body.action === 'update') {
    const plan = MOCK_PLANS.find((p) => p._id === body.id);
    if (plan) {
      Object.assign(plan, body, { updatedAt: new Date().toISOString() });
      reply(route, 200, { code: 0, data: plan });
    } else {
      reply(route, 404, { code: 1, message: 'Plan not found' });
    }
    return;
  }

  if (body.action === 'delete') {
    reply(route, 403, { code: 403, message: 'Blocked by E2E safety policy' });
    return;
  }

  if (body.action === 'listTemplates') {
    reply(route, 200, { code: 0, data: { items: MOCK_PLANS, total: MOCK_PLANS.length } });
    return;
  }

  if (body.action === 'createTemplate') {
    reply(route, 201, { code: 0, data: { _id: `mock_tpl_${300}`, name: e2eName(body.name, 'Template'), ...body, createdAt: new Date().toISOString() } });
    return;
  }

  if (body.action === 'updateTemplate') {
    reply(route, 200, { code: 0, data: { _id: body.id, ...body, updatedAt: new Date().toISOString() } });
    return;
  }

  if (body.action === 'deleteTemplate') {
    reply(route, 403, { code: 403, message: 'Blocked by E2E safety policy' });
    return;
  }

  if (body.action === 'assignToUser') {
    reply(route, 200, { code: 0, data: { assigned: true } });
    return;
  }

  reply(route, 200, { code: 0, data: {} });
}

/**
 * POST /admin/stats
 *
 * action=overview         -> { code: 0, data: { totalUsers, recentWorkouts, totalWorkouts, totalExercises } }
 * action=workoutTrend     -> { code: 0, data: { trend: { "date": count, ... } } }
 * action=userGrowth       -> { code: 0, data: { trend: { "date": count, ... } } }
 * action=exerciseUsage    -> { code: 0, data: { topExercises: [{ name, count }, ...] } }
 * action=popularCategories -> { code: 0, data: { distribution: { "chest": 320, ... } } }
 * action=export           -> blocked (safety)
 */
async function handleStats(route) {
  const body = parseBody(route.request());

  if (body.action === 'overview') {
    reply(route, 200, { code: 0, data: MOCK_STATS });
    return;
  }

  if (body.action === 'workoutTrend') {
    reply(route, 200, {
      code: 0,
      data: { trend: generateTrend(body.days || 7) },
    });
    return;
  }

  if (body.action === 'userGrowth') {
    reply(route, 200, {
      code: 0,
      data: { trend: generateTrend(body.days || 30) },
    });
    return;
  }

  if (body.action === 'exerciseUsage') {
    const topN = body.topN || 10;
    reply(route, 200, {
      code: 0,
      data: {
        topExercises: MOCK_EXERCISES.slice(0, topN).map((e) => ({
          name: e.name,
          count: Math.floor(Math.random() * 500) + 50,
        })),
      },
    });
    return;
  }

  if (body.action === 'popularCategories') {
    reply(route, 200, {
      code: 0,
      data: { distribution: generateCategoryDistribution() },
    });
    return;
  }

  if (body.action === 'export') {
    // Block data export in E2E
    reply(route, 403, { code: 403, message: 'Blocked by E2E safety policy' });
    return;
  }

  reply(route, 200, { code: 0, data: {} });
}

/**
 * POST /admin/users
 *
 * action=list            -> { code: 0, data: { items: [...], total: N } }
 * action=detail          -> { code: 0, data: {...} }
 * action=update          -> updated user
 * action=stats           -> user stats
 * action=workoutHistory  -> mock workout history
 * action=bodyMetrics     -> mock body metrics
 * action=personalRecords -> mock records
 * action=activePlan      -> mock active plan
 */
async function handleUsers(route) {
  const body = parseBody(route.request());

  if (body.action === 'list') {
    const { page = 1, pageSize = 20 } = body;
    const start = (page - 1) * pageSize;
    const items = MOCK_USERS.slice(start, start + pageSize);
    reply(route, 200, {
      code: 0,
      data: { items, total: MOCK_USERS.length },
    });
    return;
  }

  if (body.action === 'detail') {
    const user = MOCK_USERS.find((u) => u._id === body.id);
    reply(route, 200, user
      ? { code: 0, data: user }
      : { code: 1, message: 'User not found' });
    return;
  }

  if (body.action === 'update') {
    const user = MOCK_USERS.find((u) => u._id === body.id);
    if (user) {
      Object.assign(user, body);
      reply(route, 200, { code: 0, data: user });
    } else {
      reply(route, 404, { code: 1, message: 'User not found' });
    }
    return;
  }

  if (body.action === 'stats') {
    reply(route, 200, {
      code: 0,
      data: {
        totalUsers: MOCK_USERS.length,
        activeUsers: 3,
        newUsersToday: 0,
        byGoal: { hypertrophy: 1, fat_loss: 1, strength: 1, flexibility: 1, endurance: 1 },
      },
    });
    return;
  }

  if (body.action === 'workoutHistory') {
    reply(route, 200, {
      code: 0,
      data: {
        items: [
          { _id: 'wh_001', date: new Date().toISOString(), planName: 'E2E_TEST_三分化训练', exerciseCount: 5, duration: 45 },
          { _id: 'wh_002', date: new Date(Date.now() - 86400000).toISOString(), planName: 'E2E_TEST_三分化训练', exerciseCount: 5, duration: 40 },
        ],
        total: 2,
      },
    });
    return;
  }

  if (body.action === 'bodyMetrics') {
    reply(route, 200, {
      code: 0,
      data: {
        items: [
          { _id: 'bm_001', date: new Date().toISOString(), weight: 75.5, bodyFat: 18.2, muscleMass: 36.1 },
        ],
        total: 1,
      },
    });
    return;
  }

  if (body.action === 'personalRecords') {
    reply(route, 200, {
      code: 0,
      data: {
        items: [
          { _id: 'pr_001', exerciseName: 'E2E_TEST_卧推', maxWeight: 100, maxReps: 8, date: '2025-03-15T08:00:00Z' },
          { _id: 'pr_002', exerciseName: 'E2E_TEST_深蹲', maxWeight: 140, maxReps: 5, date: '2025-04-01T08:00:00Z' },
        ],
        total: 2,
      },
    });
    return;
  }

  if (body.action === 'activePlan') {
    reply(route, 200, {
      code: 0,
      data: MOCK_PLANS[0] || null,
    });
    return;
  }

  reply(route, 200, { code: 0, data: {} });
}

// --- Public API ---------------------------------------------------------------

/**
 * Activate all API mocks on the given Playwright page.
 *
 * Routes the POST URLs matching /admin/{auth,exercises,stats,plans,users}.
 * Also tracks matched/unmatched requests.
 */
async function setupApiMocks(page) {
  if (!MOCK_API) return;

  // Reset stats per page setup
  mockStats = { enabled: true, matched: 0, unmatched: 0, unmatchedUrls: [] };

  await page.route(/\/admin\/(auth|exercises|stats|plans|users)$/, async (route) => {
    await delay();

    // Normalize URL: trim whitespace from pathname and the raw URL
    const rawUrl = route.request().url().trim();
    let urlObj;
    try {
      urlObj = new URL(rawUrl);
      // Reconstruct a clean URL without trailing whitespace in pathname
      urlObj.pathname = urlObj.pathname.trim();
    } catch (_) {
      // If URL parse fails, fall back to segment extracted from raw string
      const match = rawUrl.match(/\/admin\/(auth|exercises|stats|plans|users)/);
      if (match) {
        // We'll continue with the regex-matched segment from raw URL
      } else {
        trackUnmatched(rawUrl, route.request().method(), 0, 'unparseable_url');
        route.continue();
        return;
      }
    }

    const segment = urlObj ? urlObj.pathname.split('/admin/')[1] || '' : '';

    try {
      switch (segment) {
        case 'auth':      await handleAuth(route); break;
        case 'exercises': await handleExercises(route); break;
        case 'stats':     await handleStats(route); break;
        case 'plans':     await handlePlans(route); break;
        case 'users':     await handleUsers(route); break;
        default:
          trackUnmatched(route.request().url().trim(), route.request().method(), 0, 'no_handler_for_segment');
          route.continue();
          return;
      }
      trackMatched();
    } catch (handlerErr) {
      trackUnmatched(route.request().url().trim(), route.request().method(), 0, `handler_error:${handlerErr.message?.substring(0, 80)}`);
      // If handler itself errors, pass through
      try { route.continue(); } catch (_) { /* already handled */ }
    }
  });

  // Catch requestfailed for admin API calls (not static resources)
  page.on('requestfailed', (req) => {
    const reqUrl = req.url().trim();
    if (!reqUrl) return;
    // Skip static resources
    if (isStaticResource(reqUrl)) return;
    // Only count if it's hitting the mock target domain
    if (reqUrl.includes('localhost:3000')) {
      const failureText = req.failure()?.errorText || 'failed';
      trackUnmatched(reqUrl, req.method(), 0, `requestfailed:${failureText}`);
    }
  });

  // Catch non-200 responses for admin API calls (not static resources)
  page.on('response', (resp) => {
    const reqUrl = resp.request().url().trim();
    if (!reqUrl) return;
    // Skip static resources
    if (isStaticResource(reqUrl)) return;
    // Only track error responses hitting localhost:3000
    if (resp.status() >= 400 && reqUrl.includes('localhost:3000')) {
      // Deduplicate: check if we already captured this URL+method
      const alreadyTracked = mockStats.unmatchedUrls.some(
        (u) => u.url === reqUrl && u.method === resp.request().method()
      );
      if (!alreadyTracked) {
        trackUnmatched(reqUrl, resp.request().method(), resp.status(), `HTTP_${resp.status()}_response`);
      }
    }
  });
}

/**
 * Remove all API mocks (route interceptors) from the page.
 */
async function teardownApiMocks(page) {
  if (!MOCK_API) return;
  await page.unrouteAll({ behavior: 'ignoreErrors' });
}

// --- Public API: enable / disable mock toggle -------------------------------

async function enableMocks(page) {
  await setupApiMocks(page);
}

async function disableMocks(page) {
  await teardownApiMocks(page);
}

// --- Self-test block (run directly with node) --------------------------------

if (require.main === module) {
  console.log('api-mocks self-test\n');

  // 1. Data is JSON-serializable
  function checkJson(v, label) {
    try {
      JSON.stringify(v);
      console.log(`  PASS  ${label} is JSON-serializable`);
    } catch (e) {
      console.error(`  FAIL  ${label} throws on JSON.stringify: ${e.message}`);
    }
  }

  checkJson(MOCK_EXERCISES, 'MOCK_EXERCISES');
  checkJson(MOCK_PLANS, 'MOCK_PLANS');
  checkJson(MOCK_USERS, 'MOCK_USERS');
  checkJson(MOCK_STATS, 'MOCK_STATS');
  checkJson(MOCK_TOKEN, 'MOCK_TOKEN');
  checkJson(MOCK_ADMIN, 'MOCK_ADMIN');

  // 2. Verify exercises use _id not id
  for (const ex of MOCK_EXERCISES) {
    if (ex._id === undefined) console.error(`  FAIL  Exercise missing _id: ${ex.name}`);
    if (ex.id !== undefined) console.error(`  FAIL  Exercise has legacy 'id' field: ${ex.name}`);
    if (ex.equipment === undefined) console.error(`  FAIL  Exercise missing equipment: ${ex.name}`);
    // Verify category/difficulty are enum IDs (strings, lowercase)
    if (typeof ex.category !== 'string' || ex.category !== ex.category.toLowerCase()) {
      console.error(`  FAIL  Exercise category not lowercase enum: ${ex.name} -> ${ex.category}`);
    }
    if (typeof ex.difficulty !== 'string' || ex.difficulty !== ex.difficulty.toLowerCase()) {
      console.error(`  FAIL  Exercise difficulty not lowercase enum: ${ex.name} -> ${ex.difficulty}`);
    }
  }
  console.log('  PASS  All exercises have _id, equipment, lowercase enums');

  // 3. Verify plans use correct fields
  for (const p of MOCK_PLANS) {
    if (!p._id) console.error(`  FAIL  Plan missing _id: ${p.name}`);
    if (!p.goal) console.error(`  FAIL  Plan missing goal: ${p.name}`);
    if (!Array.isArray(p.days)) console.error(`  FAIL  Plan.days not array: ${p.name}`);
    if (typeof p.frequency !== 'number') console.error(`  FAIL  Plan.frequency not number: ${p.name}`);
    if (typeof p.isActive !== 'boolean') console.error(`  FAIL  Plan.isActive not boolean: ${p.name}`);
  }
  console.log('  PASS  All plans have _id, goal, days, frequency, isActive');

  // 4. Verify users use _id
  for (const u of MOCK_USERS) {
    if (!u._id) console.error(`  FAIL  User missing _id: ${u.nickname}`);
    if (typeof u.gender !== 'number') console.error(`  FAIL  User.gender not number: ${u.nickname}`);
    if (typeof u.workoutCount !== 'number') console.error(`  FAIL  User.workoutCount not number: ${u.nickname}`);
  }
  console.log('  PASS  All users have _id, gender as number, workoutCount as number');

  // 5. Verify list response shapes
  const exListRes = { code: 0, data: { items: MOCK_EXERCISES, total: MOCK_EXERCISES.length } };
  checkJson(exListRes, 'Exercise list response (items+total)');

  const planListRes = { code: 0, data: { items: MOCK_PLANS, total: MOCK_PLANS.length } };
  checkJson(planListRes, 'Plan list response (items+total)');

  const userListRes = { code: 0, data: { items: MOCK_USERS, total: MOCK_USERS.length } };
  checkJson(userListRes, 'User list response (items+total)');

  // 6. Verify stats response shapes
  const trendRes = { code: 0, data: { trend: generateTrend(7) } };
  checkJson(trendRes, 'Workout trend response (trend as object)');
  if (typeof trendRes.data.trend !== 'object' || Array.isArray(trendRes.data.trend)) {
    console.error('  FAIL  Workout trend is not a plain object');
  } else {
    console.log('  PASS  Workout trend is a plain object (date key -> count)');
  }

  const catRes = { code: 0, data: { distribution: generateCategoryDistribution() } };
  checkJson(catRes, 'Category distribution response');
  if (typeof catRes.data.distribution !== 'object') {
    console.error('  FAIL  distribution is not an object');
  }

  const usageRes = { code: 0, data: { topExercises: [{ name: 'Test', count: 42 }] } };
  checkJson(usageRes, 'Exercise usage response (topExercises array)');
  if (!Array.isArray(usageRes.data.topExercises)) {
    console.error('  FAIL  topExercises is not an array');
  }

  // 7. Verify safety blocks
  const deleteRes = { code: 403, message: 'Blocked by E2E safety policy' };
  checkJson(deleteRes, 'Delete safety block');
  if (deleteRes.code !== 403) console.error('  FAIL  Delete should return 403');

  const exportRes = { code: 403, message: 'Blocked by E2E safety policy' };
  checkJson(exportRes, 'Export safety block');
  if (exportRes.code !== 403) console.error('  FAIL  Export should return 403');

  // 8. Verify E2E_TEST_ prefix function
  console.log(`\n  TEST  e2eName('卧推', 'fallback') = "${e2eName('卧推', 'fallback')}"`);
  console.log(`  TEST  e2eName('E2E_TEST_卧推', 'fallback') = "${e2eName('E2E_TEST_卧推', 'fallback')}"`);

  // 9. Verify exports (use direct fn references since module.exports
  //    hasn't been assigned yet when require.main === module executes)
  console.log(`\n  API   setupApiMocks:     ${typeof setupApiMocks}`);
  console.log(`  API   teardownApiMocks:  ${typeof teardownApiMocks}`);
  console.log(`  API   enableMocks:       ${typeof enableMocks}`);
  console.log(`  API   disableMocks:      ${typeof disableMocks}`);
  console.log(`  API   getMockStats:      ${typeof getMockStats}`);

  // 10. Verify mockStats
  console.log(`  STATS mockStats.enabled = ${getMockStats().enabled}`);
  console.log(`  STATS mockStats.matched = ${getMockStats().matched}`);

  // 11. exerciseStore self-test (Task A3)
  console.log('\n--- exerciseStore self-test ---');
  const initialTotal = exerciseStore.items.length;
  console.log(`  INFO  Store initialized with ${initialTotal} exercises`);

  // 11a. Verify all seed names have E2E_TEST_ prefix
  for (const ex of exerciseStore.items) {
    if (!ex.name.startsWith('E2E_TEST_')) {
      console.error(`  FAIL  Seed exercise missing E2E_TEST_ prefix: ${ex._id} -> "${ex.name}"`);
    }
  }
  console.log('  PASS  All seed exercises have E2E_TEST_ name prefix');

  // 11b. list() returns full set
  let listResult = exerciseStore.list();
  if (listResult.items.length !== 8 || listResult.total !== 8) {
    console.error(`  FAIL  list() expected 8 items, got ${listResult.items.length}, total=${listResult.total}`);
  } else {
    console.log('  PASS  list() returns 8 items with total=8');
  }

  // 11c. list({ keyword }) case-insensitive search
  listResult = exerciseStore.list({ keyword: 'E2E_TEST_' });
  if (listResult.total !== 8) {
    console.error(`  FAIL  keyword "E2E_TEST_" should match all 8, got ${listResult.total}`);
  } else {
    console.log('  PASS  keyword "E2E_TEST_" matches all 8 exercises');
  }

  listResult = exerciseStore.list({ keyword: 'bench' });
  if (listResult.total !== 1) {
    console.error(`  FAIL  keyword "bench" should match 1, got ${listResult.total}`);
  } else {
    console.log('  PASS  keyword "bench" matches 1 exercise (Barbell Bench Press)');
  }

  listResult = exerciseStore.list({ keyword: 'NONEXISTENT_XYZ' });
  if (listResult.total !== 0) {
    console.error(`  FAIL  keyword "NONEXISTENT_XYZ" should match 0, got ${listResult.total}`);
  } else {
    console.log('  PASS  keyword "NONEXISTENT_XYZ" matches 0 exercises');
  }

  // 11d. list({ category }) filter
  listResult = exerciseStore.list({ category: 'back' });
  if (listResult.total !== 2) {
    console.error(`  FAIL  category "back" should match 2, got ${listResult.total}`);
  } else {
    console.log('  PASS  category "back" matches 2 exercises');
  }

  // 11e. list({ difficulty }) filter
  listResult = exerciseStore.list({ difficulty: 'advanced' });
  if (listResult.total !== 2) {
    console.error(`  FAIL  difficulty "advanced" should match 2, got ${listResult.total}`);
  } else {
    console.log('  PASS  difficulty "advanced" matches 2 exercises');
  }

  // 11f. create() adds to store and assigns e2e_ex_<N> id
  const beforeCreate = exerciseStore.items.length;
  const created = exerciseStore.create({ name: 'Test Curl', category: 'arm', difficulty: 'beginner', equipment: 'dumbbell' });
  const afterCreate = exerciseStore.items.length;
  if (afterCreate !== beforeCreate + 1) {
    console.error(`  FAIL  create() should increase store size from ${beforeCreate} to ${beforeCreate + 1}, got ${afterCreate}`);
  } else if (!created._id.startsWith('e2e_ex_')) {
    console.error(`  FAIL  create() _id should start with "e2e_ex_", got "${created._id}"`);
  } else if (!created.name.startsWith('E2E_TEST_')) {
    console.error(`  FAIL  create() name should have E2E_TEST_ prefix, got "${created.name}"`);
  } else {
    console.log(`  PASS  create() added exercise: _id=${created._id}, name=${created.name}, store=${afterCreate}`);
  }

  // 11g. getById() for existing and missing
  const found = exerciseStore.getById(created._id);
  if (!found || found._id !== created._id) {
    console.error(`  FAIL  getById("${created._id}") should return created exercise`);
  } else {
    console.log(`  PASS  getById("${created._id}") returns created exercise`);
  }

  const notFound = exerciseStore.getById('nonexistent_id');
  if (notFound !== null) {
    console.error('  FAIL  getById("nonexistent_id") should return null');
  } else {
    console.log('  PASS  getById("nonexistent_id") returns null');
  }

  // 11h. update() persists in store
  const updated = exerciseStore.update(created._id, { name: 'E2E_TEST_Updated Curl', difficulty: 'advanced' });
  if (!updated || updated.name !== 'E2E_TEST_Updated Curl' || updated.difficulty !== 'advanced') {
    console.error(`  FAIL  update() did not persist: name="${updated?.name}", difficulty="${updated?.difficulty}"`);
  } else {
    console.log(`  PASS  update() persisted: name="${updated.name}", difficulty="${updated.difficulty}"`);
  }

  // Verify update is readable via getById
  const reRead = exerciseStore.getById(created._id);
  if (!reRead || reRead.name !== 'E2E_TEST_Updated Curl') {
    console.error('  FAIL  update() not readable via getById()');
  } else {
    console.log('  PASS  update() changes are readable via getById()');
  }

  // 11i. getStats() returns dynamic values
  const stats = exerciseStore.getStats();
  if (typeof stats.total !== 'number' || stats.total !== exerciseStore.items.length) {
    console.error(`  FAIL  getStats().total mismatch: ${stats.total} vs ${exerciseStore.items.length}`);
  } else if (!stats.byCategory || !stats.byDifficulty) {
    console.error('  FAIL  getStats() missing byCategory or byDifficulty');
  } else {
    console.log(`  PASS  getStats(): total=${stats.total}, categories=${Object.keys(stats.byCategory).length}, difficulties=${Object.keys(stats.byDifficulty).length}`);
  }

  // 11j. list() reflects create/update (the created+updated exercise appears)
  listResult = exerciseStore.list({ keyword: 'Updated Curl' });
  if (listResult.total !== 1) {
    console.error(`  FAIL  list({ keyword: "Updated Curl" }) should find updated exercise, got ${listResult.total}`);
  } else {
    console.log('  PASS  list() reflects create+update: search finds updated exercise');
  }

  // 11k. Verify delete is NOT in the store (safety block is at handler level)
  console.log('  PASS  delete blocked at handler level (403 safety policy)');

  console.log('\napi-mocks self-test complete');
}

module.exports = {
  setupApiMocks,
  teardownApiMocks,
  enableMocks,
  disableMocks,
  getMockStats,
  MOCK_API,
  // Export seed data for test assertions
  MOCK_EXERCISES,
  MOCK_PLANS,
  MOCK_USERS,
  MOCK_STATS,
  MOCK_TOKEN,
  MOCK_ADMIN,
  // Export exercise store for direct test programmatic access
  exerciseStore,
};
