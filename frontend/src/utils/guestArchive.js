// 访客本机体质暂存与登录后自动认领工具（不侵入 api/index.js，避免并行冲突）
// 依托既有的 shiyang_constitution_local_v1 本地暂存，补充作答快照与已认领时间戳，
// 让未登录完成 67 题测评的用户在「我的」页可直看结果/生成体质名片，登录后自动归入云端档案。
import { getLocalConstitution, saveRecord } from '../api'

const ANSWERS_KEY = 'shiyang_constitution_answers_v1'
const CLAIMED_TS_KEY = 'shiyang_constitution_claimed_ts_v1'

export const CODE_NAME = {
  pinghe: '平和质', qixu: '气虚质', yangxu: '阳虚质',
  yinxu: '阴虚质', tanshi: '痰湿质', shire: '湿热质',
  xueyu: '血瘀质', qiyu: '气郁质', tebing: '特禀质',
}

// 测评提交时记录作答快照；若当时已登录，直接标记该时间戳已同步，避免重复认领
export function recordQuizSnapshot(answers, alreadySynced = false) {
  try {
    const local = getLocalConstitution()
    if (answers && typeof answers === 'object') {
      localStorage.setItem(ANSWERS_KEY, JSON.stringify(answers))
    }
    if (alreadySynced && local?.ts) {
      localStorage.setItem(CLAIMED_TS_KEY, String(local.ts))
    }
  } catch { /* 存储受限时静默 */ }
}

function loadSavedAnswers() {
  try { return JSON.parse(localStorage.getItem(ANSWERS_KEY) || '{}') || {} } catch { return {} }
}

function fmtLocalTime(ts) {
  if (!ts) return '本机暂存'
  const d = new Date(ts)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 将本机暂存转换为与后端 listRecords 单条一致的结构，供 Me.vue 与 ConstitutionCard 直接复用
export function getGuestConstitutionRecord() {
  const local = getLocalConstitution()
  if (!local?.judged) return null
  const j = local.judged
  const mainCode = j.main || j.combined?.[0] || 'pinghe'
  const mainName = j.main_name || CODE_NAME[mainCode] || '平和质'
  const combined = (j.combined || []).map((c) => CODE_NAME[c] || c)
  const claimedTs = localStorage.getItem(CLAIMED_TS_KEY)
  return {
    id: 'local',
    main_code: mainCode,
    main_name: mainName,
    combined,
    transformed: local.transformed || {},
    created_at: fmtLocalTime(local.ts),
    ts: local.ts,
    synced: !!local.ts && claimedTs === String(local.ts),
    judged: j,
  }
}

// 是否存在尚未同步到云端账号的本机测评结果
export function getPendingClaimRecord() {
  const rec = getGuestConstitutionRecord()
  if (!rec || rec.synced) return null
  return rec
}

// 登录/注册成功后自动把本机未归档的测评写入云端档案（幂等，同一 ts 只认领一次）
export async function claimGuestConstitutionIfNeeded() {
  const rec = getPendingClaimRecord()
  if (!rec) return null
  try {
    await saveRecord(rec.judged, rec.transformed, loadSavedAnswers(), null)
    if (rec.ts) localStorage.setItem(CLAIMED_TS_KEY, String(rec.ts))
    return rec
  } catch {
    // 认领失败不阻断登录主流程，下次仍可重试
    return null
  }
}

export const GUEST_EXTRA_KEYS = [
  'shiyang_constitution_local_v1',
  ANSWERS_KEY,
  CLAIMED_TS_KEY,
]
