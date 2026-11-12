const NATIONAL_SOURCE = '《太原理工大学本科生国家奖助学金管理办法》（校学〔2024〕21号）'
const SCHOOL_SOURCE = '《软件学院本科生荣誉称号及优秀学生奖学金评定实施办法（试行）》（2025年3月修订）'

const statusMeta = {
  pass: { icon: '✅', label: '满足' },
  fail: { icon: '❌', label: '不满足' },
  missing: { icon: '❓', label: '信息缺失' },
  review: { icon: '🔎', label: '需人工复核' },
}

const gradeMap = {
  大一: 1, 一年级: 1,
  大二: 2, 二年级: 2,
  大三: 3, 三年级: 3,
  大四: 4, 四年级: 4,
  大五: 5, 五年级: 5,
}

function firstNumber(text, patterns) {
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (match) return Number(match[1])
  }
  return null
}

function explicitBoolean(text, positivePatterns, negativePatterns) {
  if (negativePatterns.some((pattern) => pattern.test(text))) return false
  if (positivePatterns.some((pattern) => pattern.test(text))) return true
  return null
}

function distinctMatches(text, labels) {
  return labels.filter((label) => text.includes(label))
}

export function extractProfile(text) {
  const gradeLabel = Object.keys(gradeMap).find((label) => text.includes(label)) || null
  const failedCourses = /(?:无|没有)(?:挂科|不及格课程|不及格科目)/.test(text)
    ? 0
    : firstNumber(text, [/(?:挂科|不及格(?:课程|科目)?)\s*(\d+)\s*(?:科|门)?/, /(\d+)\s*(?:科|门)(?:挂科|不及格)/])
  const disciplineFree = explicitBoolean(
    text,
    [/(?:无|没有)(?:违法违纪|违纪|纪律处分|处分)/],
    [/(?:有|受到|曾受)(?:违法违纪|违纪|纪律处分|处分)/],
  )
  const hardshipRecognized = explicitBoolean(
    text,
    [/(?:已|已经)(?:被)?认定为家庭经济困难/, /家庭经济困难(?:学生)?认定(?:通过|成功)/, /(?:困难|贫困)(?:学生)?(?:已)?入库/, /在困难生库/],
    [/(?:未|没有)(?:被)?认定为家庭经济困难/, /困难认定(?:未通过|失败)/, /未入困难生库/],
  )
  const honorLabels = distinctMatches(text, ['三好学生', '优秀学生干部', '学业优秀个人', '实践优秀个人', '文体优秀个人'])
  const explicitHonorCount = firstNumber(text, [/(\d+)\s*项(?:及以上)?优秀个人荣誉称号/])

  return {
    raw: text,
    grade: gradeLabel ? gradeMap[gradeLabel] : null,
    gradeLabel,
    academicRank: firstNumber(text, [
      /(?:专业|学业|加权学习成绩|学习成绩)(?:成绩)?排名(?:位于|在|为)?(?:年级专业)?\s*(?:前)?\s*(\d+(?:\.\d+)?)\s*%/,
      /(?:专业|学业|加权学习成绩|学习成绩)\s*(?:前)\s*(\d+(?:\.\d+)?)\s*%/,
    ]),
    comprehensiveRank: firstNumber(text, [
      /(?:综测|综合素质测评|素质综合测评|综合测评)(?:成绩)?排名?(?:位于|在|为)?(?:年级专业)?\s*(?:前)?\s*(\d+(?:\.\d+)?)\s*%/,
      /(?:综测|综合素质测评|素质综合测评|综合测评)\s*(?:前)\s*(\d+(?:\.\d+)?)\s*%/,
    ]),
    failedCourses,
    disciplineFree,
    fullTime: explicitBoolean(text, [/全日制/], [/非全日制/]),
    undergraduate: explicitBoolean(text, [/(?:本科生|本科在校生|本科学生)/], [/(?:研究生|专科生)/]),
    nationality: explicitBoolean(text, [/(?:中国籍|中华人民共和国国籍)/], [/(?:外籍|非中国籍)/]),
    registered: explicitBoolean(text, [/(?:已|按时|正常)注册/], [/(?:未|没有)注册/]),
    integrity: explicitBoolean(text, [/(?:诚实守信|道德品质优良)/], [/(?:失信|弄虚作假|道德品质不合格)/]),
    studyPositive: explicitBoolean(text, [/(?:学习态度端正|刻苦勤奋|学习刻苦|积极上进)/], [/(?:学习态度不端正)/]),
    hardshipRecognized,
    hardshipProof: /(?:贫困证明|困难证明|低保证明)/.test(text),
    specialHardship: /(?:建档立卡|脱贫家庭|低保家庭|城乡低保|特困救助|孤儿|残疾|烈士子女|突发严重困难)/.test(text),
    softwareCollege: explicitBoolean(text, [/软件学院/], [/(?:机械|材料|化工|建筑|矿业)学院/]),
    basicQualityPassed: explicitBoolean(text, [/(?:三项成绩(?:均)?合格|基本素质(?:要求)?合格)/], [/(?:三项成绩|基本素质).{0,5}不合格/]),
    gradeRecordComplete: explicitBoolean(text, [/(?:成绩记录完整|教务系统成绩完整)/], [/(?:成绩记录不全|教务系统成绩不全)/]),
    honorCount: explicitHonorCount ?? (honorLabels.length || null),
    honorLabels,
    achievementEvidence: distinctMatches(text, ['国家级竞赛', '省级竞赛', '竞赛一等奖', '创新发明', '学术论文', '三好学生', '优秀学生干部']),
  }
}

function condition(label, status, observed, rule, source, missingPrompt = label) {
  return { label, status, observed, rule, source, missingPrompt }
}

function boolCondition(profile, key, label, expected, rule, source, missingPrompt = label) {
  const value = profile[key]
  if (value === null) return condition(label, 'missing', '未提供', rule, source, missingPrompt)
  const passed = value === expected
  return condition(label, passed ? 'pass' : 'fail', passed ? '已明确满足' : '已明确不满足', rule, source, missingPrompt)
}

function maxCondition(profile, key, label, max, rule, source, missingPrompt = label) {
  const value = profile[key]
  if (value === null) return condition(label, 'missing', '未提供', rule, source, missingPrompt)
  return condition(label, value <= max ? 'pass' : 'fail', `${value}%`, rule, source, missingPrompt)
}

function minCondition(profile, key, label, min, unit, rule, source, missingPrompt = label) {
  const value = profile[key]
  if (value === null) return condition(label, 'missing', '未提供', rule, source, missingPrompt)
  return condition(label, value >= min ? 'pass' : 'fail', `${value}${unit}`, rule, source, missingPrompt)
}

function gradeCondition(profile, source) {
  if (profile.grade === null) {
    return condition('年级要求', 'missing', '未提供', '二年级及以上', source, '年级（大一/大二/大三/大四）')
  }
  return condition('年级要求', profile.grade >= 2 ? 'pass' : 'fail', profile.gradeLabel, '二年级及以上', source)
}

function fullTimeUndergraduateCondition(profile, source) {
  if (profile.fullTime === false || profile.undergraduate === false) {
    return condition('全日制本科生身份', 'fail', '已明确不符合', '全日制本科在校生', source)
  }
  if (profile.fullTime === null || profile.undergraduate === null) {
    return condition('全日制本科生身份', 'missing', '未完整提供', '全日制本科在校生', source, '是否为全日制本科在校生')
  }
  return condition('全日制本科生身份', 'pass', '全日制本科生', '全日制本科在校生', source)
}

function noFailedCourses(profile, max, source) {
  if (profile.failedCourses === null) {
    return condition('不及格课程', 'missing', '未提供', max === 0 ? '无不及格课程' : `不超过${max}科`, source, '参评学年挂科/不及格课程数量')
  }
  return condition('不及格课程', profile.failedCourses <= max ? 'pass' : 'fail', `${profile.failedCourses}科`, max === 0 ? '无不及格课程' : `不超过${max}科`, source)
}

function nationalCommon(profile, clause) {
  const source = `${NATIONAL_SOURCE}${clause}`
  return [
    boolCondition(profile, 'nationality', '中国国籍', true, '具有中华人民共和国国籍', source, '是否具有中华人民共和国国籍'),
    boolCondition(profile, 'registered', '学籍注册', true, '遵守校规并按规定注册', source, '是否已按规定注册'),
    boolCondition(profile, 'disciplineFree', '遵纪守法', true, '遵守法律和学校规章制度', source, '是否无违法违纪或纪律处分'),
    boolCondition(profile, 'integrity', '诚信与品德', true, '诚实守信、道德品质优良', source, '是否诚实守信、道德品质优良'),
  ]
}

function evaluateNationalScholarship(profile) {
  const source = `${NATIONAL_SOURCE}第10—11条，PDF第4页`
  const conditions = [...nationalCommon(profile, '第10条，PDF第4页'), gradeCondition(profile, source), fullTimeUndergraduateCondition(profile, source)]
  const academic = profile.academicRank
  const comprehensive = profile.comprehensiveRank
  if (academic === null || comprehensive === null) {
    conditions.push(condition('排名条件', 'missing', `学业：${academic ?? '未提供'}；综测：${comprehensive ?? '未提供'}`, '两项均前10%；或两项均前30%且有特别突出表现', source, '学业排名和综合测评排名'))
  } else if (academic <= 10 && comprehensive <= 10) {
    conditions.push(condition('排名条件', 'pass', `学业前${academic}%，综测前${comprehensive}%`, '两项均位于前10%', source))
  } else if (academic <= 30 && comprehensive <= 30) {
    conditions.push(condition('排名条件', 'review', `学业前${academic}%，综测前${comprehensive}%`, '超出前10%但均在前30%时，必须具备政策规定的特别突出表现', source, '特别突出表现的奖项级别与证明材料'))
    conditions.push(profile.achievementEvidence.length
      ? condition('突出表现', 'review', profile.achievementEvidence.join('、'), '社会实践、创新能力、综合素质等方面特别突出，需学院审核证明材料', source)
      : condition('突出表现', 'missing', '未提供可核验材料', '社会实践、创新能力、综合素质等方面特别突出', source, '突出表现及对应证明材料'))
  } else {
    conditions.push(condition('排名条件', 'fail', `学业前${academic}%，综测前${comprehensive}%`, '两项均前10%；例外路径也要求两项均在前30%', source))
  }
  conditions.push(noFailedCourses(profile, 0, source))
  return summarize('国家奖学金', conditions, source)
}

function evaluateNationalInspirational(profile) {
  const source = `${NATIONAL_SOURCE}第12条，PDF第6页`
  const conditions = [
    ...nationalCommon(profile, '第10条，PDF第4页'),
    gradeCondition(profile, source),
    fullTimeUndergraduateCondition(profile, source),
    maxCondition(profile, 'academicRank', '学业成绩排名', 50, '年级专业前50%', source, '学业成绩排名百分比'),
    maxCondition(profile, 'comprehensiveRank', '综合测评排名', 15, '原则上年级专业前15%', source, '综合测评排名百分比'),
    noFailedCourses(profile, 0, source),
    boolCondition(profile, 'hardshipRecognized', '家庭经济困难认定', true, '参评学年被认定为家庭经济困难学生', source, '是否已通过当学年家庭经济困难认定'),
  ]
  return summarize('国家励志奖学金', conditions, source)
}

function evaluateNationalGrant(profile) {
  const source = `${NATIONAL_SOURCE}第13—14条，PDF第6页`
  const conditions = [
    ...nationalCommon(profile, '第10条，PDF第4页'),
    fullTimeUndergraduateCondition(profile, source),
    boolCondition(profile, 'studyPositive', '学习态度', true, '学习态度端正、刻苦勤奋、积极上进', source, '学习态度是否端正、积极上进'),
    boolCondition(profile, 'hardshipRecognized', '家庭经济困难认定', true, '参评学年被认定为家庭经济困难学生', source, '是否已通过当学年家庭经济困难认定'),
  ]
  const result = summarize('国家助学金', conditions, source)
  if (profile.specialHardship) result.notes.push('检测到政策列举的特殊困难情形，可优先申请一等国家助学金；最终档次仍由学校评议确定。')
  if (profile.hardshipProof && profile.hardshipRecognized === null) result.notes.push('“有贫困/困难证明”不等于“已通过家庭经济困难认定”，当前不能据此判定符合。')
  return result
}

function evaluateSchoolScholarship(profile, tier) {
  const configs = {
    1: { name: '软件学院优秀学生一等奖学金', rank: 20, honors: 3, failed: 0, amount: 1800, ratio: '不超过参评专业学生总数的3%' },
    2: { name: '软件学院优秀学生二等奖学金', rank: 50, honors: 2, failed: 1, amount: 1200, ratio: '不超过参评专业学生总数的10%' },
    3: { name: '软件学院优秀学生三等奖学金', rank: 60, honors: 1, failed: 1, amount: 600, ratio: '不超过参评专业学生总数的20%' },
  }
  const config = configs[tier]
  const source = `${SCHOOL_SOURCE}第8—10条，PDF第5—6页`
  const conditions = [
    boolCondition(profile, 'softwareCollege', '学院范围', true, '评定对象为软件学院普通全日制在籍本科生', source, '是否为软件学院学生'),
    fullTimeUndergraduateCondition(profile, source),
    boolCondition(profile, 'basicQualityPassed', '基本素质', true, '综合评价基本素质三项成绩均须合格', source, '综合评价三项基本素质成绩是否均合格'),
    boolCondition(profile, 'registered', '学籍注册', true, '按时注册', source, '是否按时注册'),
    boolCondition(profile, 'disciplineFree', '纪律处分', true, '无违法违纪行为，评定学年无纪律处分', source, '评定学年是否无违纪处分'),
    boolCondition(profile, 'gradeRecordComplete', '成绩记录', true, '教务系统学习成绩完整', source, '教务系统学习成绩是否完整'),
    maxCondition(profile, 'academicRank', '学业成绩排名', config.rank, `原则上专业前${config.rank}%`, source, '学业成绩排名百分比'),
    minCondition(profile, 'honorCount', '优秀个人荣誉称号', config.honors, '项', `至少${config.honors}项`, source, '优秀个人荣誉称号数量'),
    noFailedCourses(profile, config.failed, source),
  ]
  const result = summarize(config.name, conditions, source)
  result.notes.push(`非毕业年级奖励标准为${config.amount}元，评选比例${config.ratio}；满足条件后仍按综合评价排名择优评定。`)
  return result
}

function summarize(name, conditions, source) {
  const counts = conditions.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1
    return acc
  }, { pass: 0, fail: 0, missing: 0, review: 0 })
  let status = '初步符合'
  if (counts.fail) status = '暂不符合'
  else if (counts.missing) status = '信息不足'
  else if (counts.review) status = '需人工复核'
  return { name, status, conditions, counts, source, notes: [] }
}

function selectPrograms(text, profile) {
  if (/国家励志奖学金/.test(text)) return ['inspirational']
  if (/国家助学金/.test(text)) return ['grant']
  if (/国家奖学金/.test(text)) return ['national']
  if (/一等(?:优秀学生)?奖学金|一等奖学金/.test(text)) return ['school1']
  if (/二等(?:优秀学生)?奖学金|二等奖学金/.test(text)) return ['school2']
  if (/三等(?:优秀学生)?奖学金|三等奖学金/.test(text)) return ['school3']
  if (/优秀学生奖学金/.test(text)) return ['school1', 'school2', 'school3']
  if (/(?:困难|贫困|低保|助学金)/.test(text)) return ['inspirational', 'grant']
  if (profile.softwareCollege === true) return ['national', 'school1', 'school2', 'school3']
  return ['national', 'inspirational', 'grant']
}

function formatProfile(profile) {
  const facts = []
  if (profile.gradeLabel) facts.push(`年级：${profile.gradeLabel}`)
  if (profile.fullTime !== null || profile.undergraduate !== null) facts.push(`学生身份：${profile.fullTime === true ? '全日制' : profile.fullTime === false ? '非全日制' : '全日制情况未知'}${profile.undergraduate === true ? '本科生' : profile.undergraduate === false ? '非本科生' : '，学历层次未知'}`)
  if (profile.academicRank !== null) facts.push(`学业排名：前${profile.academicRank}%`)
  if (profile.comprehensiveRank !== null) facts.push(`综合测评排名：前${profile.comprehensiveRank}%`)
  if (profile.failedCourses !== null) facts.push(`不及格课程：${profile.failedCourses}科`)
  if (profile.disciplineFree !== null) facts.push(`纪律情况：${profile.disciplineFree ? '无违纪处分' : '存在违纪或处分'}`)
  if (profile.hardshipRecognized !== null) facts.push(`困难认定：${profile.hardshipRecognized ? '已认定' : '未认定'}`)
  else if (profile.hardshipProof) facts.push('困难材料：仅提到有证明，未说明是否通过困难认定')
  if (profile.honorCount !== null) facts.push(`优秀个人荣誉称号：${profile.honorCount}项`)
  return facts
}

function formatResult(result) {
  const statusIcon = result.status === '初步符合' ? '🟢' : result.status === '暂不符合' ? '🔴' : '🟡'
  const verified = result.conditions.length - result.counts.missing
  const lines = [`### ${statusIcon} ${result.name}：${result.status}`, '', `已核验 ${verified}/${result.conditions.length} 项条件；满足 ${result.counts.pass} 项、不满足 ${result.counts.fail} 项、缺失 ${result.counts.missing} 项、人工复核 ${result.counts.review} 项。`, '']
  for (const item of result.conditions) {
    const meta = statusMeta[item.status]
    lines.push(`- ${meta.icon} **${item.label}｜${meta.label}**：${item.observed}。政策要求：${item.rule}。`)
  }
  for (const note of result.notes) lines.push(`- ℹ️ ${note}`)
  return lines.join('\n')
}

export function evaluateMessage(text) {
  const profile = extractProfile(text)
  const programIds = selectPrograms(text, profile)
  const evaluators = {
    national: evaluateNationalScholarship,
    inspirational: evaluateNationalInspirational,
    grant: evaluateNationalGrant,
    school1: (value) => evaluateSchoolScholarship(value, 1),
    school2: (value) => evaluateSchoolScholarship(value, 2),
    school3: (value) => evaluateSchoolScholarship(value, 3),
  }
  const results = programIds.map((id) => evaluators[id](profile))
  const facts = formatProfile(profile)
  const missingPrompts = [...new Set(results.flatMap((result) => result.conditions.filter((item) => item.status === 'missing').map((item) => item.missingPrompt)))].slice(0, 6)
  const sources = [...new Set(results.map((result) => result.source))]

  const answer = [
    '## 本地政策规则评估',
    '',
    '> 本结果由浏览器内的确定性规则引擎生成，不调用大模型。未提供的信息一律标记为“信息缺失”，不会自行推断。',
    '',
    '### 已提取的明确事实',
    '',
    ...(facts.length ? facts.map((item) => `- ${item}`) : ['- 暂未从输入中提取到可用于硬条件判断的明确事实。']),
    '',
    ...results.flatMap((result) => [formatResult(result), '']),
    '### 仍需补充',
    '',
    ...(missingPrompts.length ? missingPrompts.map((item) => `- ${item}`) : ['- 硬条件信息已基本齐全；仍需以学院材料审核和名额排序为准。']),
    '',
    '### 政策来源',
    '',
    ...sources.map((source, index) => `${index + 1}. ${source}`),
    '',
    '> 规则版本基于仓库内现有政策文件。政策更新、例外情形及证明材料有效性需由学院最终审核。',
  ].join('\n')

  const suggestions = [
    missingPrompts[0] ? `补充信息：${missingPrompts[0]}` : '比较其他奖助学金项目',
    missingPrompts[1] ? `补充信息：${missingPrompts[1]}` : '查看政策来源和评审边界',
    '生成这次评估的申请报告',
  ]

  return { profile, results, answer, suggestions, missingPrompts, sources }
}

export function buildRuleTrace(text, evaluation) {
  const knownFacts = formatProfile(evaluation.profile)
  const totals = evaluation.results.reduce((acc, result) => {
    for (const key of Object.keys(acc)) acc[key] += result.counts[key]
    return acc
  }, { pass: 0, fail: 0, missing: 0, review: 0 })
  return [
    { type: 'todo', items: [
      { content: '从自然语言提取明确学生事实', status: 'completed' },
      { content: '选择匹配的政策项目与条款', status: 'completed' },
      { content: '执行确定性资格规则', status: 'completed' },
      { content: '汇总缺失信息与政策依据', status: 'completed' },
    ] },
    { type: 'tool_call', name: 'extract_local_student_profile', args: { text } },
    { type: 'tool_result', name: 'extract_local_student_profile', preview: knownFacts.length ? `提取到 ${knownFacts.length} 项明确事实：${knownFacts.join('；')}` : '未提取到可核验的硬条件事实。' },
    { type: 'tool_call', name: 'load_local_policy_rules', args: { programs: evaluation.results.map((item) => item.name) } },
    { type: 'tool_result', name: 'load_local_policy_rules', preview: `加载 ${evaluation.results.length} 个评估项目，来源：${evaluation.sources.join('；')}` },
    { type: 'tool_call', name: 'evaluate_policy_conditions', args: { unknown_as: 'missing', deterministic: true } },
    { type: 'tool_result', name: 'evaluate_policy_conditions', preview: `规则结果：满足 ${totals.pass} 项、不满足 ${totals.fail} 项、缺失 ${totals.missing} 项、需复核 ${totals.review} 项。` },
  ]
}
