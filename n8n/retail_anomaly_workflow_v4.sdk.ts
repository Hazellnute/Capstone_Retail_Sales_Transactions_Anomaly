import { workflow, node, trigger, sticky, ifElse, merge, languageModel, outputParser, expr } from '@n8n/workflow-sdk';

const scheduleMonthly = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.3,
  config: {
    name: 'Jadwal Cek Anomali (Bulanan)',
    parameters: {
      rule: { interval: [{ field: 'months', monthsInterval: 1, triggerAtDayOfMonth: 1, triggerAtHour: 7, triggerAtMinute: 0 }] }
    },
    position: [0, 208]
  },
  output: [{}]
});

const readTransactions = node({
  type: 'n8n-nodes-base.googleSheets',
  version: 4.7,
  config: {
    name: 'Ambil Data Transaksi (Mentah)',
    parameters: {
      resource: 'sheet',
      operation: 'read',
      documentId: { __rl: true, mode: 'list', value: '1BXSCVwFXfmDdqGJVdPiACSMAgmSf27ug0ttLzk3ZNvE', cachedResultName: 'Retail_sales_transactions_clean_0' },
      sheetName: { __rl: true, mode: 'list', value: '503275821', cachedResultName: 'retail_sales_transactions_clean' },
      options: {}
    },
    credentials: { googleSheetsOAuth2Api: { id: '0YxDcAuapV0xU5Fp', name: 'Google Sheets account 38' } },
    position: [224, 112]
  },
  output: [{ transaction_id: 'TRX20702', transaction_datetime: '2025-03-01 22:15:00', transaction_hour: 22, store_name: 'Store Jakarta 01', store_city: 'Jakarta', channel: 'offline', member_id: 'M001', member_tier: 'Silver', item_tier_requirement: 'Gold', qty: 3, net_amount_idr: 5550000, card_last4: '1234', issuing_bank: 'BCA' }]
});

const readMembers = node({
  type: 'n8n-nodes-base.googleSheets',
  version: 4.7,
  config: {
    name: 'Ambil Data Member (Mentah)',
    parameters: {
      resource: 'sheet',
      operation: 'read',
      documentId: { __rl: true, mode: 'list', value: '1iaLomQrV9kx6xQGwsgUUAtn8-EdYoTXf39YJoCeHwvY', cachedResultName: 'member_master_analyze' },
      sheetName: { __rl: true, mode: 'list', value: '231344787', cachedResultName: 'member_master_analyze' },
      options: {}
    },
    credentials: { googleSheetsOAuth2Api: { id: '0YxDcAuapV0xU5Fp', name: 'Google Sheets account 38' } },
    position: [224, 304]
  },
  output: [{ member_id: 'M001', member_name: 'Member Satu', member_tier: 'Silver', phone_number: '081234567890', email: 'm001@example.com' }]
});

const combineSources = merge({
  version: 3.2,
  config: {
    name: 'Gabungkan Transaksi & Member',
    parameters: { mode: 'append' },
    position: [448, 208]
  }
});

const signalPrepCode =
  'const items = $input.all();\n' +
  'const transactions = items.filter(i => i.json.transaction_id !== undefined && String(i.json.transaction_id).trim() !== "").map(i => i.json);\n' +
  'const members = items.filter(i => i.json.transaction_id === undefined && i.json.member_id !== undefined).map(i => i.json);\n' +
  '\n' +
  '// ===== Parameter rule (ubah di sini bila SOP berubah) =====\n' +
  'const OPERATING_HOUR_START = 9;\n' +
  'const OPERATING_HOUR_END = 21; // transaksi pukul 21:xx masih dianggap dalam jam operasional\n' +
  'const IMPOSSIBLE_TRAVEL_MINUTES = 90;\n' +
  'const TIER_QTY_LIMIT = { platinum: 1, gold: 2 };\n' +
  'const TIER_RANK = { regular: 0, silver: 1, gold: 2, platinum: 3 };\n' +
  '\n' +
  'const norm = v => (v === undefined || v === null) ? "" : String(v).trim();\n' +
  'const rank = tier => { const k = norm(tier).toLowerCase(); return Object.prototype.hasOwnProperty.call(TIER_RANK, k) ? TIER_RANK[k] : -1; };\n' +
  'const cityOf = t => norm(t.store_city || t.geo_area);\n' +
  'const isOnline = t => norm(t.channel).toLowerCase() === "online" || cityOf(t).toLowerCase() === "online";\n' +
  'const cardKeyOf = t => {\n' +
  '  if (norm(t.card_key)) return norm(t.card_key);\n' +
  '  const last4 = norm(t.card_last4);\n' +
  '  return last4 ? last4 + "|" + norm(t.issuing_bank).toUpperCase() : "";\n' +
  '};\n' +
  'const parseTime = v => { const d = new Date(norm(v).replace(" ", "T")); return isNaN(d.getTime()) ? null : d; };\n' +
  'const pushUnique = (obj, key, val) => { if (!obj[key]) obj[key] = []; if (obj[key].indexOf(val) === -1) obj[key].push(val); };\n' +
  '\n' +
  '// ===== Master member =====\n' +
  'const memberById = {};\n' +
  'members.forEach(m => { const id = norm(m.member_id); if (id) memberById[id] = m; });\n' +
  '\n' +
  '// ===== R6: kontak duplikat (telepon dinormalisasi ke digit, email lowercase) =====\n' +
  'const phoneGroups = {};\n' +
  'const emailGroups = {};\n' +
  'members.forEach(m => {\n' +
  '  const id = norm(m.member_id);\n' +
  '  if (!id) return;\n' +
  '  const phone = norm(m.phone_number).replace(/\\D/g, "");\n' +
  '  const email = norm(m.email).toLowerCase();\n' +
  '  if (phone) pushUnique(phoneGroups, phone, id);\n' +
  '  if (email) pushUnique(emailGroups, email, id);\n' +
  '});\n' +
  'const duplicateEvidence = {};\n' +
  'const collectDup = (groups, label) => Object.keys(groups).forEach(k => {\n' +
  '  const ids = groups[k];\n' +
  '  if (ids.length < 2) return;\n' +
  '  ids.forEach(id => pushUnique(duplicateEvidence, id, label + " sama dengan member " + ids.filter(x => x !== id).join(", ")));\n' +
  '});\n' +
  'collectDup(phoneGroups, "nomor telepon");\n' +
  'collectDup(emailGroups, "email");\n' +
  '\n' +
  '// ===== R1: kartu dipakai >1 member (hanya jika card_key / card_last4 tersedia) =====\n' +
  'const cardGroups = {};\n' +
  'transactions.forEach(t => {\n' +
  '  const key = cardKeyOf(t);\n' +
  '  const mid = norm(t.member_id);\n' +
  '  if (key && mid) pushUnique(cardGroups, key, mid);\n' +
  '});\n' +
  '\n' +
  '// ===== R5: impossible travel antar kota fisik =====\n' +
  'const byMember = {};\n' +
  'transactions.forEach(t => { const mid = norm(t.member_id); if (mid) { if (!byMember[mid]) byMember[mid] = []; byMember[mid].push(t); } });\n' +
  'const travelEvidence = {};\n' +
  'Object.keys(byMember).forEach(mid => {\n' +
  '  const list = byMember[mid].filter(t => parseTime(t.transaction_datetime)).sort((a, b) => parseTime(a.transaction_datetime) - parseTime(b.transaction_datetime));\n' +
  '  for (let i = 1; i < list.length; i++) {\n' +
  '    const prev = list[i - 1];\n' +
  '    const curr = list[i];\n' +
  '    if (isOnline(prev) || isOnline(curr)) continue;\n' +
  '    const prevCity = cityOf(prev);\n' +
  '    const currCity = cityOf(curr);\n' +
  '    if (!prevCity || !currCity || prevCity.toLowerCase() === currCity.toLowerCase()) continue;\n' +
  '    const diff = (parseTime(curr.transaction_datetime) - parseTime(prev.transaction_datetime)) / 60000;\n' +
  '    if (diff >= 0 && diff < IMPOSSIBLE_TRAVEL_MINUTES) {\n' +
  '      const ev = prevCity + " pada " + prev.transaction_datetime + " lalu " + currCity + " pada " + curr.transaction_datetime + " (selisih " + Math.round(diff) + " menit)";\n' +
  '      pushUnique(travelEvidence, norm(prev.transaction_id), ev);\n' +
  '      pushUnique(travelEvidence, norm(curr.transaction_id), ev);\n' +
  '    }\n' +
  '  }\n' +
  '});\n' +
  '\n' +
  'const hourOf = t => {\n' +
  '  const h = Number(t.transaction_hour);\n' +
  '  if (norm(t.transaction_hour) !== "" && !isNaN(h)) return h;\n' +
  '  const m = norm(t.transaction_datetime).match(/[T ](\\d{1,2}):/);\n' +
  '  return m ? Number(m[1]) : null;\n' +
  '};\n' +
  '\n' +
  'const verifiedAt = new Date().toISOString();\n' +
  'return transactions.map(t => {\n' +
  '  const tid = norm(t.transaction_id);\n' +
  '  const mid = norm(t.member_id);\n' +
  '\n' +
  '  const cardKey = cardKeyOf(t);\n' +
  '  const sharers = cardKey ? (cardGroups[cardKey] || []).filter(id => id !== mid) : [];\n' +
  '  const r1 = sharers.length > 0;\n' +
  '\n' +
  '  const memberTier = (memberById[mid] && memberById[mid].member_tier) || t.member_tier;\n' +
  '  const itemRank = rank(t.item_tier_requirement);\n' +
  '  const r2 = itemRank > 0 && itemRank > rank(memberTier);\n' +
  '\n' +
  '  const hour = hourOf(t);\n' +
  '  const r3 = hour !== null && (hour < OPERATING_HOUR_START || hour > OPERATING_HOUR_END);\n' +
  '\n' +
  '  const tierKey = norm(t.item_tier_requirement).toLowerCase();\n' +
  '  const qty = Number(t.qty) || 0;\n' +
  '  const qtyLimit = TIER_QTY_LIMIT[tierKey];\n' +
  '  const r4 = qtyLimit !== undefined && qty > qtyLimit;\n' +
  '\n' +
  '  const r5 = Boolean(travelEvidence[tid]);\n' +
  '  const r6 = Boolean(mid && duplicateEvidence[mid]);\n' +
  '\n' +
  '  const rules = [\n' +
  '    { code: "R1", flag: r1, field: "flag_R1_card_sharing", ev: r1 ? "Kartu yang sama juga dipakai oleh member " + sharers.join(", ") : "Tidak ada indikasi kartu dipakai member lain pada batch ini" },\n' +
  '    { code: "R2", flag: r2, field: "flag_R2_tier_mismatch", ev: r2 ? "Item membutuhkan tier " + t.item_tier_requirement + " namun member bertier " + (memberTier || "tidak diketahui") : "Tier item sesuai atau di bawah tier member" },\n' +
  '    { code: "R3", flag: r3, field: "flag_R3_outside_hours", ev: r3 ? "Transaksi pukul " + hour + ":00, di luar jam operasional " + OPERATING_HOUR_START + ":00-" + OPERATING_HOUR_END + ":59" : "Transaksi dalam jam operasional" },\n' +
  '    { code: "R4", flag: r4, field: "flag_R4_bulk_limited", ev: r4 ? "Item " + t.item_tier_requirement + " dibeli " + qty + " pcs, melebihi batas " + qtyLimit : "Kuantitas dalam batas wajar" },\n' +
  '    { code: "R5", flag: r5, field: "flag_R5_impossible_travel", ev: r5 ? travelEvidence[tid].join("; ") : "Tidak ada transaksi lain dari member ini di kota berbeda dalam waktu singkat" },\n' +
  '    { code: "R6", flag: r6, field: "flag_R6_duplicate_account", ev: r6 ? duplicateEvidence[mid].join("; ") : "Tidak ada kontak (telepon/email) yang sama dengan member lain" }\n' +
  '  ];\n' +
  '\n' +
  '  const out = Object.assign({}, t);\n' +
  '  rules.forEach(r => { out[r.field] = r.flag; out["evidence_" + r.code] = r.ev; });\n' +
  '  const hits = rules.filter(r => r.flag);\n' +
  '  out.anomaly_count = hits.length;\n' +
  '  out.triggered_rules = hits.map(r => r.code).join(", ");\n' +
  '  out.evidence_summary = hits.map(r => r.code + ": " + r.ev).join("\\n");\n' +
  '  out.is_anomaly = hits.length > 0;\n' +
  '  out.is_anomaly_num = hits.length > 0 ? 1 : 0;\n' +
  '  out.verified_at = verifiedAt;\n' +
  '  return { json: out };\n' +
  '});';

const signalPrep = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Candidate Signal Prep (R1-R6)',
    parameters: { mode: 'runOnceForAllItems', language: 'javaScript', jsCode: signalPrepCode },
    position: [672, 208]
  },
  output: [{ transaction_id: 'TRX20702', store_name: 'Store Jakarta 01', member_id: 'M001', net_amount_idr: 5550000, anomaly_count: 2, triggered_rules: 'R2, R4', evidence_summary: 'R2: Item membutuhkan tier Gold namun member bertier Silver\nR4: Item Gold dibeli 3 pcs, melebihi batas 2', is_anomaly: true, is_anomaly_num: 1, verified_at: '2026-09-27T00:00:00.000Z' }]
});

const writeVerification = node({
  type: 'n8n-nodes-base.googleSheets',
  version: 4.7,
  config: {
    name: 'Tulis ke Spreadsheet Verifikasi',
    onError: 'continueRegularOutput',
    parameters: {
      resource: 'sheet',
      operation: 'appendOrUpdate',
      documentId: { __rl: true, mode: 'id', value: '1_5s--rAZnDR8PntoJ9ZdunM0_YyEwq5yta1zbrTc0-Q', cachedResultName: 'retail_sales_transactions_clean (verifikasi)' },
      sheetName: { __rl: true, mode: 'list', value: '503275821', cachedResultName: 'retail_sales_transactions_clean' },
      columns: { mappingMode: 'autoMapInputData', value: {}, matchingColumns: ['transaction_id'], schema: [] },
      options: {}
    },
    credentials: { googleSheetsOAuth2Api: { id: '0YxDcAuapV0xU5Fp', name: 'Google Sheets account 38' } },
    position: [896, 64]
  },
  output: [{ transaction_id: 'TRX20702' }]
});

const filterAnomaly = node({
  type: 'n8n-nodes-base.filter',
  version: 2.3,
  config: {
    name: 'Filter Anomali (is_anomaly = true)',
    parameters: {
      conditions: {
        options: { caseSensitive: true, leftValue: '', typeValidation: 'loose' },
        conditions: [{ leftValue: expr('{{ $json.is_anomaly }}'), operator: { type: 'boolean', operation: 'true', singleValue: true } }],
        combinator: 'and'
      },
      options: {}
    },
    position: [896, 304]
  },
  output: [{ transaction_id: 'TRX20702', store_name: 'Store Jakarta 01', member_id: 'M001', net_amount_idr: 5550000, anomaly_count: 2, triggered_rules: 'R2, R4', evidence_summary: 'R2: ...\nR4: ...', is_anomaly: true }]
});

const dedupAlert = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Cek Belum Pernah Dialert',
    parameters: {
      resource: 'row',
      operation: 'rowNotExists',
      dataTableId: { __rl: true, mode: 'id', value: 't9Rn64YIO0TyjpDQ', cachedResultName: 'agentic_sent_anomaly_alerts' },
      matchType: 'allConditions',
      filters: { conditions: [{ keyName: 'transaction_id', condition: 'eq', keyValue: expr('{{ $json.transaction_id }}') }] }
    },
    position: [1120, 304]
  },
  output: [{ transaction_id: 'TRX20702', store_name: 'Store Jakarta 01', member_id: 'M001', net_amount_idr: 5550000, anomaly_count: 2, triggered_rules: 'R2, R4', evidence_summary: 'R2: ...\nR4: ...', is_anomaly: true }]
});

const rankCode =
  '// Urutkan kandidat paling berisiko dulu: jumlah rule terpicu, lalu nilai transaksi.\n' +
  'const MAX_ALERTS = 3;\n' +
  'return $input.all()\n' +
  '  .map((item, index) => ({ json: item.json, pairedItem: { item: index } }))\n' +
  '  .sort((a, b) => (Number(b.json.anomaly_count) - Number(a.json.anomaly_count)) || ((Number(b.json.net_amount_idr) || 0) - (Number(a.json.net_amount_idr) || 0)))\n' +
  '  .slice(0, MAX_ALERTS);';

const rankCandidates = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Prioritaskan Kandidat (Top 3)',
    parameters: { mode: 'runOnceForAllItems', language: 'javaScript', jsCode: rankCode },
    position: [1344, 304]
  },
  output: [{ transaction_id: 'TRX20702', store_name: 'Store Jakarta 01', member_id: 'M001', net_amount_idr: 5550000, anomaly_count: 2, triggered_rules: 'R2, R4', evidence_summary: 'R2: ...\nR4: ...', is_anomaly: true }]
});

const classifierModel = languageModel({
  type: '@n8n/n8n-nodes-langchain.lmChatDeepSeek',
  version: 1,
  config: {
    name: 'DeepSeek Chat Model (Classifier)',
    parameters: { model: 'deepseek-chat', options: { temperature: 0.1 } },
    credentials: { deepSeekApi: { id: 'wvbPMO1NBaZ2VV13', name: 'DeepSeek account 2' } },
    position: [1520, 528]
  }
});

const prioritySchema = outputParser({
  type: '@n8n/n8n-nodes-langchain.outputParserStructured',
  version: 1.3,
  config: {
    name: 'Risk Priority Schema',
    parameters: {
      schemaType: 'manual',
      inputSchema: JSON.stringify({
        type: 'object',
        properties: {
          priority: { type: 'string', enum: ['High', 'Medium', 'Low'] },
          rationale: { type: 'string' }
        },
        required: ['priority', 'rationale']
      })
    },
    position: [1680, 528]
  }
});

const riskClassifier = node({
  type: '@n8n/n8n-nodes-langchain.agent',
  version: 3.1,
  config: {
    name: 'Risk Classifier Agent',
    parameters: {
      promptType: 'define',
      text: expr('Transaksi {{ $json.transaction_id }} di {{ $json.store_name }}, member {{ $json.member_id }}, nilai Rp{{ $json.net_amount_idr }}.\n\nRule yang terkonfirmasi anomali ({{ $json.anomaly_count }} total):\n{{ $json.evidence_summary }}\n\nTentukan prioritas risiko (High/Medium/Low) untuk transaksi ini beserta alasannya.'),
      hasOutputParser: true,
      options: {
        systemMessage: 'Anda adalah asisten audit internal yang menilai prioritas risiko investigasi untuk transaksi yang sudah terkonfirmasi memiliki indikator anomali. Gunakan kerangka berikut:\n\nHIGH: banyak indikator sekaligus, nilai transaksi signifikan, ada pola berulang, atau bukti lintas-transaksi yang kuat (mis. card sharing dengan banyak member, duplicate account dengan banyak kontak).\nMEDIUM: satu indikator signifikan dengan nilai atau frekuensi yang cukup berarti.\nLOW: satu indikator terisolasi dengan nilai kecil dan/atau ada penjelasan yang masuk akal.\n\nPrioritas ini menunjukkan urgensi investigasi, BUKAN kesimpulan kecurangan. Dasarkan penilaian hanya pada bukti (evidence) yang diberikan. Jangan gunakan istilah fraud/penipuan - gunakan "indikator anomali" dan "memerlukan review". Jawab priority hanya dengan salah satu dari: High, Medium, Low.'
      }
    },
    subnodes: { model: classifierModel, outputParser: prioritySchema },
    position: [1568, 304]
  },
  output: [{ output: { priority: 'High', rationale: 'Dua indikator terkonfirmasi (R2, R4) dengan nilai transaksi signifikan.' } }]
});

const mergePriorityCode =
  'const original = $("Prioritaskan Kandidat (Top 3)").item.json;\n' +
  'const classified = $json.output || {};\n' +
  'const PRIORITY = { high: "High", medium: "Medium", low: "Low" };\n' +
  'const key = String(classified.priority || "").trim().toLowerCase();\n' +
  'const merged = Object.assign({}, original);\n' +
  'merged.priority = PRIORITY[key] || "Medium";\n' +
  'merged.priority_rationale = classified.rationale || "Output classifier tidak valid; prioritas default Medium dan perlu review manual.";\n' +
  'return { json: merged };';

const mergePriority = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Gabungkan Prioritas',
    parameters: { mode: 'runOnceForEachItem', language: 'javaScript', jsCode: mergePriorityCode },
    position: [1904, 304]
  },
  output: [{ transaction_id: 'TRX20702', store_name: 'Store Jakarta 01', member_id: 'M001', net_amount_idr: 5550000, anomaly_count: 2, triggered_rules: 'R2, R4', evidence_summary: 'R2: ...\nR4: ...', priority: 'High', priority_rationale: 'Dua indikator terkonfirmasi.' }]
});

const drafterModel = languageModel({
  type: '@n8n/n8n-nodes-langchain.lmChatDeepSeek',
  version: 1,
  config: {
    name: 'DeepSeek Chat Model (Drafter)',
    parameters: { model: 'deepseek-chat', options: { temperature: 0.3 } },
    credentials: { deepSeekApi: { id: 'wvbPMO1NBaZ2VV13', name: 'DeepSeek account 2' } },
    position: [2080, 528]
  }
});

const draftSchema = outputParser({
  type: '@n8n/n8n-nodes-langchain.outputParserStructured',
  version: 1.3,
  config: {
    name: 'Alert Draft Schema',
    parameters: {
      schemaType: 'fromJson',
      jsonSchemaExample: '{ "subject": "[Audit Alert - Medium] TX TRX20702 - 2 indikator anomali", "body_html": "<p>Terdeteksi transaksi dengan indikator anomali...</p>" }'
    },
    position: [2240, 528]
  }
});

const alertDrafter = node({
  type: '@n8n/n8n-nodes-langchain.agent',
  version: 3.1,
  config: {
    name: 'Alert Drafting Agent',
    parameters: {
      promptType: 'define',
      text: expr('Transaksi {{ $json.transaction_id }} di {{ $json.store_name }}, member {{ $json.member_id }}, nilai Rp{{ $json.net_amount_idr }}.\nJumlah indikator anomali terkonfirmasi: {{ $json.anomaly_count }} ({{ $json.triggered_rules }}).\nEvidence:\n{{ $json.evidence_summary }}\n\nPrioritas risiko: {{ $json.priority }}. Alasan: {{ $json.priority_rationale }}\n\nSusun subject email dan body HTML untuk alert audit internal.'),
      hasOutputParser: true,
      options: {
        systemMessage: 'Anda adalah asisten audit internal yang menyusun draft email alert untuk tim audit. Gunakan bahasa profesional, evidence-first, istilah "indikator anomali" dan "memerlukan review" - JANGAN PERNAH gunakan kata "fraud" atau "penipuan" atau menyimpulkan kecurangan. Sesuaikan tingkat detail dengan prioritas: HIGH -> body lengkap dan rinci (semua evidence, tekankan urgensi review), MEDIUM -> body cukup ringkas (poin utama saja), LOW -> body singkat (satu-dua kalimat). Subject harus menyertakan prioritas dan transaction_id. Body dalam format HTML sederhana (paragraf/list), sertakan catatan bahwa ini indikator yang memerlukan review, bukan kesimpulan pelanggaran.'
      }
    },
    subnodes: { model: drafterModel, outputParser: draftSchema },
    position: [2128, 304]
  },
  output: [{ output: { subject: '[Audit Alert - High] TX TRX20702 - 2 indikator anomali', body_html: '<p>Terdeteksi transaksi dengan indikator anomali...</p>' } }]
});

const mergeDraftCode =
  'const original = $("Gabungkan Prioritas").item.json;\n' +
  'const draft = $json.output || {};\n' +
  'const merged = Object.assign({}, original);\n' +
  'merged.alert_subject = draft.subject || ("[Audit Alert - " + original.priority + "] TX " + original.transaction_id + " - " + original.anomaly_count + " indikator anomali");\n' +
  'merged.alert_body_html = draft.body_html || ("<p>Transaksi " + original.transaction_id + " memiliki indikator anomali (" + original.triggered_rules + ") yang memerlukan review.</p><pre>" + original.evidence_summary + "</pre>");\n' +
  'return { json: merged };';

const mergeDraft = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Gabungkan Draft Alert',
    parameters: { mode: 'runOnceForEachItem', language: 'javaScript', jsCode: mergeDraftCode },
    position: [2464, 304]
  },
  output: [{ transaction_id: 'TRX20702', store_name: 'Store Jakarta 01', member_id: 'M001', net_amount_idr: 5550000, triggered_rules: 'R2, R4', priority: 'High', alert_subject: '[Audit Alert - High] TX TRX20702', alert_body_html: '<p>...</p>' }]
});

const needsApproval = ifElse({
  version: 2.3,
  config: {
    name: 'Perlu Approval? (Prioritas HIGH)',
    parameters: {
      conditions: {
        options: { caseSensitive: true, leftValue: '', typeValidation: 'strict' },
        conditions: [{ leftValue: expr('{{ $json.priority }}'), operator: { type: 'string', operation: 'equals' }, rightValue: 'High' }],
        combinator: 'and'
      },
      options: {}
    },
    position: [2688, 304]
  }
});

const sendApproval = node({
  type: 'n8n-nodes-base.gmail',
  version: 2.2,
  config: {
    name: 'Kirim & Minta Approval (High)',
    parameters: {
      resource: 'message',
      operation: 'sendAndWait',
      sendTo: 'nathalia.triandini@gmail.com',
      subject: expr('[HIGH - Perlu Approval] {{ $json.alert_subject }}'),
      message: expr('{{ $json.alert_body_html }}<hr><p><strong>Prioritas risiko: HIGH.</strong> Mohon klik tombol di bawah setelah review dilakukan untuk menandai transaksi ini sebagai sudah ditinjau.</p>'),
      responseType: 'approval',
      approvalOptions: { values: { approvalType: 'single', approveLabel: 'Approve (Sudah Direview)' } },
      options: {
        limitWaitTime: { values: { limitType: 'afterTimeInterval', resumeAmount: 24, resumeUnit: 'hours' } },
        appendAttribution: false
      }
    },
    credentials: { gmailOAuth2: { id: 'x1G0RNgZduO3RyYj', name: 'Gmail account 20' } },
    position: [2912, 208]
  },
  output: [{ data: { approved: true } }]
});

const sendAlert = node({
  type: 'n8n-nodes-base.gmail',
  version: 2.2,
  config: {
    name: 'Kirim Alert Email',
    parameters: {
      resource: 'message',
      operation: 'send',
      sendTo: 'nathalia.triandini@gmail.com',
      subject: expr('{{ $json.alert_subject }}'),
      emailType: 'html',
      message: expr('{{ $json.alert_body_html }}'),
      options: { appendAttribution: false }
    },
    credentials: { gmailOAuth2: { id: 'x1G0RNgZduO3RyYj', name: 'Gmail account 20' } },
    position: [2912, 400]
  },
  output: [{ id: 'msg-1', threadId: 'thread-1', labelIds: ['SENT'] }]
});

const logTracker = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Catat ke Log Tracker',
    parameters: {
      resource: 'row',
      operation: 'insert',
      dataTableId: { __rl: true, mode: 'id', value: 't9Rn64YIO0TyjpDQ', cachedResultName: 'agentic_sent_anomaly_alerts' },
      columns: {
        mappingMode: 'defineBelow',
        value: {
          transaction_id: expr("{{ $('Gabungkan Draft Alert').item.json.transaction_id }}"),
          anomaly_rules: expr("{{ $('Gabungkan Draft Alert').item.json.triggered_rules }}"),
          priority: expr("{{ $('Gabungkan Draft Alert').item.json.priority }}"),
          net_amount_idr: expr("{{ $('Gabungkan Draft Alert').item.json.net_amount_idr }}"),
          store_name: expr("{{ $('Gabungkan Draft Alert').item.json.store_name }}"),
          member_id: expr("{{ $('Gabungkan Draft Alert').item.json.member_id }}"),
          alerted_at: expr('{{ $now.toISO() }}')
        },
        matchingColumns: [],
        schema: [
          { id: 'transaction_id', displayName: 'transaction_id', required: false, defaultMatch: false, display: true, type: 'string', readOnly: false, removed: false },
          { id: 'anomaly_rules', displayName: 'anomaly_rules', required: false, defaultMatch: false, display: true, type: 'string', readOnly: false, removed: false },
          { id: 'priority', displayName: 'priority', required: false, defaultMatch: false, display: true, type: 'string', readOnly: false, removed: false },
          { id: 'net_amount_idr', displayName: 'net_amount_idr', required: false, defaultMatch: false, display: true, type: 'number', readOnly: false, removed: false },
          { id: 'store_name', displayName: 'store_name', required: false, defaultMatch: false, display: true, type: 'string', readOnly: false, removed: false },
          { id: 'member_id', displayName: 'member_id', required: false, defaultMatch: false, display: true, type: 'string', readOnly: false, removed: false },
          { id: 'alerted_at', displayName: 'alerted_at', required: false, defaultMatch: false, display: true, type: 'dateTime', readOnly: false, removed: false }
        ],
        attemptToConvertTypes: false,
        convertFieldsToString: false
      },
      options: {}
    },
    position: [3136, 304]
  },
  output: [{ id: 1, createdAt: '2026-09-27T00:00:00.000Z', updatedAt: '2026-09-27T00:00:00.000Z' }]
});

const ruleNote = sticky(
  '## Rule anomali (Candidate Signal Prep)\n' +
  '- **R1** Kartu sama dipakai >1 member\n' +
  '- **R2** Tier item > tier member\n' +
  '- **R3** Di luar jam operasional 09:00-21:59\n' +
  '- **R4** Qty item Platinum >1 / Gold >2\n' +
  '- **R5** Impossible travel <90 menit antar kota (offline)\n' +
  '- **R6** Telepon/email sama dengan member lain\n\n' +
  'Parameter bisa diubah di bagian atas Code node.',
  [signalPrep],
  { color: 4 }
);

const aiNote = sticky(
  '## Agentic layer\n' +
  'Risk Classifier menentukan prioritas (High/Medium/Low), Alert Drafter menyusun email. ' +
  'Prioritas HIGH butuh approval reviewer (maks 24 jam). ' +
  'Semua alert dicatat ke Data Table agar tidak dikirim ulang.',
  [riskClassifier, alertDrafter],
  { color: 6 }
);

export default workflow('retail-anomaly-v4', 'Retail Anomaly Agentic Workflow - v4 (Rebuilt)')
  .add(scheduleMonthly)
  .to(readTransactions.to(combineSources.input(0)))
  .add(scheduleMonthly)
  .to(readMembers.to(combineSources.input(1)))
  .add(combineSources)
  .to(signalPrep)
  .add(signalPrep)
  .to(writeVerification)
  .add(signalPrep)
  .to(filterAnomaly)
  .to(dedupAlert)
  .to(rankCandidates)
  .to(riskClassifier)
  .to(mergePriority)
  .to(alertDrafter)
  .to(mergeDraft)
  .to(needsApproval
    .onTrue(sendApproval.to(logTracker))
    .onFalse(sendAlert.to(logTracker)))
  .add(ruleNote)
  .add(aiNote);
