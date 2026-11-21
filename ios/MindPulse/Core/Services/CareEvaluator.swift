import Foundation

/// 主动关心评估（客户端本地镜像服务端 CareEngine 的逻辑）。
///
/// 触发条件（全部满足才出现一条提示）：
/// 1. 用户已授权对应指标；
/// 2. 每个参与评估的指标都有足够历史基线；
/// 3. 多项指标同时偏离，或单项偏离持续一段时间；
/// 4. 用户偏好未关闭。
///
/// 语言：永远不确定语气，永远不出现疾病名称或诊断分数。
struct MetricDaySnapshot: Equatable {
    var date: String
    var sleepHours: Double?
    var restingHR: Double?
    var hrvSDNN: Double?
    var steps: Int?
}

struct CareEvaluation: Equatable {
    var shouldNotify: Bool
    var message: String?
    var reasons: [String]
    var metrics: [String]
}

struct CareSettingsConfig {
    var minBaselineDays = 10
    var recentDays = 3
    var sustainedWindowDays = 7
    var sustainedMinDays = 5
    var multiMetricCount = 2
    var sleepDropRatio = 0.20
    var stepsDropRatio = 0.30
    var restingHRDelta = 8.0
    var hrvDropRatio = 0.25
}

enum CareEvaluator {
    private struct Check {
        let label: String
        let scope: HealthScope?
        let values: [Double]
        let isRiseDelta: Bool
        let threshold: Double
    }

    static func evaluate(
        snapshots: [MetricDaySnapshot],
        grantedScopes: Set<HealthScope>,
        careEnabled: Bool = true,
        settings: CareSettingsConfig = CareSettingsConfig(),
        now: Date = Date()
    ) -> CareEvaluation {
        guard careEnabled else {
            return CareEvaluation(shouldNotify: false, message: nil, reasons: [], metrics: [])
        }

        let sorted = snapshots.sorted { $0.date < $1.date }
        var deviatedLabels: [String] = []
        var sustainedLabels: [String] = []

        var checks: [Check] = []
        checks.append(Check(label: "睡眠", scope: .sleep, values: sorted.compactMap(\.sleepHours), isRiseDelta: false, threshold: settings.sleepDropRatio))
        checks.append(Check(label: "静息心率", scope: .restingHeartRate, values: sorted.compactMap(\.restingHR), isRiseDelta: true, threshold: settings.restingHRDelta))
        checks.append(Check(label: "心率变异性", scope: .hrv, values: sorted.compactMap(\.hrvSDNN), isRiseDelta: false, threshold: settings.hrvDropRatio))
        checks.append(Check(label: "活动量", scope: .steps, values: sorted.compactMap { $0.steps.map(Double.init) }, isRiseDelta: false, threshold: settings.stepsDropRatio))

        for check in checks {
            if let scope = check.scope, !grantedScopes.contains(scope) { continue }
            let baseline = Array(check.values.dropLast(settings.recentDays))
            let recent = Array(check.values.suffix(settings.recentDays))
            guard baseline.count >= settings.minBaselineDays, recent.count == settings.recentDays else { continue }

            let baselineAvg = baseline.reduce(0, +) / Double(baseline.count)
            let recentAvg = recent.reduce(0, +) / Double(recent.count)

            let isDeviated: Bool
            if check.isRiseDelta {
                isDeviated = recentAvg >= baselineAvg + check.threshold
            } else {
                isDeviated = recentAvg <= baselineAvg * (1 - check.threshold)
            }
            guard isDeviated else { continue }
            deviatedLabels.append(check.label)

            // 持续性：最近 N 天窗口中逐日偏离的天数
            if check.values.count >= settings.sustainedWindowDays {
                let window = check.values.suffix(settings.sustainedWindowDays)
                let deviatedDays = window.filter { dayValue in
                    if check.isRiseDelta {
                        return dayValue >= baselineAvg + check.threshold
                    }
                    return dayValue <= baselineAvg * (1 - check.threshold)
                }.count
                if deviatedDays >= settings.sustainedMinDays {
                    sustainedLabels.append(check.label)
                }
            }
        }

        guard !deviatedLabels.isEmpty else {
            return CareEvaluation(shouldNotify: false, message: nil, reasons: [], metrics: [])
        }

        let isMultiMetric = deviatedLabels.count >= settings.multiMetricCount
        guard isMultiMetric || !sustainedLabels.isEmpty else {
            // 单一指标、非持续的变化不足以触发（例如单次 HRV 波动）
            return CareEvaluation(shouldNotify: false, message: nil, reasons: [], metrics: [])
        }

        var reasons: [String] = ["仅使用你已明确授权的指标，且随时可以在设置中关闭"]
        let labels = Array(Set(deviatedLabels + sustainedLabels)).sorted().joined(separator: "、")
        if isMultiMetric {
            reasons.append("\(labels) 等多项指标同时出现变化")
        }
        if !sustainedLabels.isEmpty {
            reasons.append("其中变化持续了 \(settings.sustainedMinDays) 天以上")
        }
        reasons.append("这只是一次温和的观察，不是任何医学判断；也完全可能没有特别的原因")

        let message = "我注意到你最近几天的\(labels)和之前不太一样。也可能只是这段时间比较忙，或者身体在自然波动。你最近感觉怎么样？"

        return CareEvaluation(
            shouldNotify: true,
            message: message,
            reasons: reasons,
            metrics: deviatedLabels
        )
    }
}
