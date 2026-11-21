import Foundation
import HealthKit

/// HealthKit 读取服务。
///
/// 边界（与产品要求一致）：
/// - 只有用户在授权页面主动点击后才会调用 requestAuthorization；
/// - 不使用后台投递（background delivery），不会在后台偷偷读取；
/// - 只产出"按天聚合值"，不持久化任何逐分钟原始数据；
/// - 每次读取前都检查 ConsentService 的授权状态。
final class HealthKitService: ObservableObject {
    enum AuthorizationState: Equatable {
        case unsupported    // 设备不支持 HealthKit（iPad 等）
        case notRequested
        case authorized
        case denied
        case noData         // 已授权但当前没有数据
    }

    struct DailyValue: Equatable {
        let date: Date
        let value: Double
    }

    @Published var authorizationState: AuthorizationState = .notRequested

    private let healthStore = HKHealthStore()
    let isAvailable = HKHealthStore.isHealthDataAvailable()

    // MARK: - 类型定义

    private var sleepType: HKCategoryType { HKCategoryType(.sleepAnalysis) }
    private var restingHRType: HKQuantityType { HKQuantityType(.restingHeartRate) }
    private var hrvType: HKQuantityType { HKQuantityType(.heartRateVariabilitySDNN) }
    private var stepType: HKQuantityType { HKQuantityType(.stepCount) }

    var readTypes: Set<HKObjectType> {
        [sleepType, restingHRType, hrvType, stepType]
    }

    // MARK: - 授权（只在用户主动点击时调用）

    /// 返回是否获得授权。此方法必须由 HealthConsentView 的按钮触发，禁止在启动时自动调用。
    func requestAuthorization() async throws -> Bool {
        guard isAvailable else {
            authorizationState = .unsupported
            return false
        }
        do {
            // 只读取、不写入（toShare 为空）
            try await healthStore.requestAuthorization(toShare: [], read: readTypes)
            authorizationState = .authorized
            return true
        } catch {
            authorizationState = .denied
            return false
        }
    }

    // MARK: - 聚合查询

    private func dayStart(_ date: Date) -> Date {
        Calendar.current.startOfDay(for: date)
    }

    private func rangeStart(days: Int) -> Date {
        dayStart(Calendar.current.date(byAdding: .day, value: -days, to: Date()) ?? Date())
    }

    /// 步数 / 静息心率 / HRV 的按天聚合。
    func fetchDailyAggregates(metric: HealthScope, days: Int) async throws -> [DailyValue] {
        guard isAvailable else { return [] }

        let quantityType: HKQuantityType
        let options: HKStatisticsOptions
        let unit: HKUnit

        switch metric {
        case .steps:
            quantityType = stepType
            options = [.cumulativeSum]
            unit = .count()
        case .restingHeartRate:
            quantityType = restingHRType
            options = [.discreteAverage]
            unit = HKUnit.count().unitDivided(by: .minute())
        case .hrv:
            quantityType = hrvType
            options = [.discreteAverage]
            unit = .second() // SDNN 以秒存储，换算为毫秒
        case .sleep:
            return try await fetchSleepDurations(days: days)
        }

        let start = rangeStart(days: days)
        let anchor = dayStart(Date())
        let interval = DateComponents(day: 1)

        let query = HKStatisticsCollectionQuery(
            quantityType: quantityType,
            quantitySamplePredicate: nil,
            options: options,
            anchorDate: anchor,
            intervalComponents: interval
        )

        return try await withCheckedThrowingContinuation { continuation in
            query.initialResultsHandler = { _, results, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                var values: [DailyValue] = []
                results?.enumerateStatistics(from: start, to: Date()) { statistics, _ in
                    let raw: Double?
                    switch options {
                    case .cumulativeSum:
                        raw = statistics.sumQuantity()?.doubleValue(for: unit)
                    default:
                        raw = statistics.averageQuantity()?.doubleValue(for: unit)
                    }
                    let value = (metric == .hrv) ? (raw ?? 0) * 1000 : raw // 秒 → 毫秒
                    if let value, value > 0 {
                        values.append(DailyValue(date: statistics.startDate, value: value))
                    }
                }
                continuation.resume(returning: values)
            }
            healthStore.execute(query)
        }
    }

    /// 睡眠时长：汇总 AsleepCore/Deep/REM 阶段（不含清醒/在床）。
    func fetchSleepDurations(days: Int) async throws -> [DailyValue] {
        guard isAvailable else { return [] }
        let start = rangeStart(days: days)
        let predicate = HKQuery.predicateForSamples(withStart: start, end: Date(), options: .strictStartDate)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: sleepType,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: nil
            ) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                var byDay: [Date: Double] = [:]
                for sample in (samples as? [HKCategorySample]) ?? [] {
                    guard let stage = HKCategoryValueSleepAnalysis(rawValue: sample.value),
                          stage == .asleepCore || stage == .asleepDeep || stage == .asleepREM
                    else { continue }
                    let day = Calendar.current.startOfDay(for: sample.startDate)
                    byDay[day, default: 0] += sample.endDate.timeIntervalSince(sample.startDate) / 3600.0
                }
                let values = byDay
                    .filter { $0.value > 0 }
                    .sorted { $0.key < $1.key }
                    .map { DailyValue(date: $0.key, value: $0.value) }
                continuation.resume(returning: values)
            }
            healthStore.execute(query)
        }
    }

    /// 汇总最近 N 天的聚合快照（只含用户已授权的指标）。
    func buildSnapshots(days: Int, grantedScopes: Set<HealthScope>) async throws -> [(date: String, sleepHours: Double?, restingHR: Double?, hrvSDNN: Double?, steps: Int?)] {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = .current

        var byDate: [String: (Double?, Double?, Double?, Int?)] = [:]

        if grantedScopes.contains(.sleep) {
            for v in try await fetchSleepDurations(days: days) {
                let key = formatter.string(from: v.date)
                byDate[key, default: (nil, nil, nil, nil)].0 = v.value
            }
        }
        if grantedScopes.contains(.restingHeartRate) {
            for v in try await fetchDailyAggregates(metric: .restingHeartRate, days: days) {
                let key = formatter.string(from: v.date)
                byDate[key, default: (nil, nil, nil, nil)].1 = v.value
            }
        }
        if grantedScopes.contains(.hrv) {
            for v in try await fetchDailyAggregates(metric: .hrv, days: days) {
                let key = formatter.string(from: v.date)
                byDate[key, default: (nil, nil, nil, nil)].2 = v.value
            }
        }
        if grantedScopes.contains(.steps) {
            for v in try await fetchDailyAggregates(metric: .steps, days: days) {
                let key = formatter.string(from: v.date)
                byDate[key, default: (nil, nil, nil, nil)].3 = Int(v.value)
            }
        }

        return byDate
            .sorted { $0.key < $1.key }
            .map { ($0.key, $0.value.0, $0.value.1, $0.value.2, $0.value.3) }
    }
}
