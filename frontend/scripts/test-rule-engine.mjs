import assert from 'node:assert/strict'

import { evaluateMessage, extractProfile } from '../src/demo/ruleEngine.js'

const nationalPass = evaluateMessage('我是中国籍软件学院大二全日制本科生，已按时注册，诚实守信，道德品质优良，无违纪处分，无挂科，专业排名前8%，综测排名前9%，有国家级竞赛获奖，申请国家奖学金。')
assert.equal(nationalPass.results[0].name, '国家奖学金')
assert.equal(nationalPass.results[0].status, '初步符合')
assert.equal(nationalPass.results[0].counts.fail, 0)
assert.equal(nationalPass.results[0].counts.missing, 0)
assert.equal(nationalPass.results[0].conditions.some((item) => item.label === '突出表现'), false)

const nationalFail = evaluateMessage('我是中国籍大三全日制本科生，已注册，诚实守信，无处分无挂科，专业排名前40%，综测排名前20%，申请国家奖学金。')
assert.equal(nationalFail.results[0].status, '暂不符合')
assert.equal(nationalFail.results[0].counts.missing, 0)
assert.equal(nationalFail.results[0].conditions.some((item) => item.label === '突出表现'), false)

const nationalException = evaluateMessage('我是中国籍大三全日制本科生，已注册，诚实守信，无处分无挂科，专业排名前20%，综测排名前25%，申请国家奖学金。')
assert.equal(nationalException.results[0].status, '信息不足')
assert.equal(nationalException.results[0].conditions.some((item) => item.label === '突出表现' && item.status === 'missing'), true)

const proofOnly = evaluateMessage('我是全日制本科生，有贫困证明，想申请国家助学金。')
assert.equal(proofOnly.profile.hardshipProof, true)
assert.equal(proofOnly.profile.hardshipRecognized, null)
assert.equal(proofOnly.results[0].status, '信息不足')

const inspirational = evaluateMessage('我是中国籍大三全日制本科生，已按时注册，诚实守信，无违纪处分，学习刻苦，专业排名前30%，综测前10%，无挂科，已经被认定为家庭经济困难学生，申请国家励志奖学金。')
assert.equal(inspirational.results[0].counts.fail, 0)
assert.equal(inspirational.results[0].counts.missing, 0)

const schoolFirst = evaluateMessage('我是软件学院大二全日制本科生，已按时注册，无违纪处分，三项成绩均合格，教务系统成绩完整，专业排名前18%，获得3项优秀个人荣誉称号，无挂科，申请一等奖学金。')
assert.equal(schoolFirst.results[0].status, '初步符合')

const schoolSuggestion = evaluateMessage('我是软件学院大二全日制本科生，专业排名前18%，获得3项优秀个人荣誉称号，无挂科无处分，三项成绩合格，已按时注册，成绩记录完整，请评估一等奖学金。')
assert.equal(schoolSuggestion.results[0].status, '初步符合')

const parsed = extractProfile('大二，专业排名前8%，综测排名9%，挂科1门')
assert.equal(parsed.grade, 2)
assert.equal(parsed.academicRank, 8)
assert.equal(parsed.comprehensiveRank, 9)
assert.equal(parsed.failedCourses, 1)

console.log('rule-engine tests: PASS')
