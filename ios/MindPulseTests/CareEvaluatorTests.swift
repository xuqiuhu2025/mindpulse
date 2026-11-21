import XCTest
@testable import MindPulse

/// CareEvaluator：客户端主动关心逻辑（与服务端 CareEngine 同一策略）。
final class CareEvaluatorTests: XCTestCase {
    private func makeSnapshots(
        days: Int,
        baseline: MetricDaySnapshot,
        recent: MetricDaySnapshot,
        recentDays: Int = 3
    ) -> [MetricDaySnapshot] {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        let today = Date()
        var result: [MetricDaySnapshot] = []
        for i in 0..<days {
            let date = Calendar.current.date(byAdding: .day, value: -(days - 1 - i), to: today)!
            let key = formatter.string(from: date)
            let isRecent = i >= days - recentDays
            var snapshot = isRecent ? recent : baseline
            snapshot.date = key
            result.append(snapshot)
        }
        return result
    }

    private let allScopes: Set<HealthScope> = [.sleep, .restingHeartRate, .hrv, .steps]
    private let baseline = MetricDaySnapshot(date: "", sleepHours: 8, restingHR: 60, hrvSDNN: 50, steps: 8000)

    func testNoBaseline_neverGeneratesConclusion() {
        // 场景 7：没有足够历史数据时不生成健康趋势结论
        let few = makeSnapshots(days: 3, baseline: baseline, recent: baseline)
        let evaluation = CareEvaluator.evaluate(snapshots: few, grantedScopes: allScopes)
        XCTAssertFalse(evaluation.shouldNotify)
        XCTAssertNil(evaluation.message)
    }

    func testSingleShortHRVChange_doesNotInferIllness() {
        // 场景 8：单一 HRV 短时变化不能触发任何疾病判断
        var recent = baseline
        recent.hrvSDNN = 30 // 仅 HRV 下降
        let snapshots = makeSnapshots(days: 13, baseline: baseline, recent: recent)
        let evaluation = CareEvaluator.evaluate(snapshots: snapshots, grantedScopes: allScopes)
        XCTAssertFalse(evaluation.shouldNotify)
        TestSupport.assertNoDiseaseLanguage(evaluation.message ?? "")
    }

    func testMultiMetricSimultaneousChange_notifiesWithUncertainty() {
        var recent = baseline
        recent.sleepHours = 5.5 // 下降 >20%
        recent.steps = 4000     // 下降 >30%
        let snapshots = makeSnapshots(days: 13, baseline: baseline, recent: recent)
        let evaluation = CareEvaluator.evaluate(snapshots: snapshots, grantedScopes: allScopes)

        XCTAssertTrue(evaluation.shouldNotify)
        let message = evaluation.message ?? ""
        XCTAssertTrue(message.contains("和之前不太一样"))
        XCTAssertTrue(message.contains("也可能只是"))
        XCTAssertTrue(message.contains("你最近感觉怎么样"))
        XCTAssertFalse(message.contains("HRV 下降")) // 不做数值因果推断
        TestSupport.assertNoDiseaseLanguage(message)
        XCTAssertTrue(evaluation.reasons.contains { $0.contains("同时出现变化") })
    }

    func testSingleSustainedChange_notifiesGently() {
        var recent = baseline
        recent.sleepHours = 5.0
        let snapshots = makeSnapshots(days: 13, baseline: baseline, recent: recent, recentDays: 7)
        let evaluation = CareEvaluator.evaluate(snapshots: snapshots, grantedScopes: allScopes)
        XCTAssertTrue(evaluation.shouldNotify)
        XCTAssertTrue(evaluation.reasons.contains { $0.contains("持续") })
        TestSupport.assertNoDiseaseLanguage(evaluation.message ?? "")
    }

    func testRevokedScope_isNeverEvaluated() {
        var recent = baseline
        recent.sleepHours = 5.5
        recent.steps = 4000
        let snapshots = makeSnapshots(days: 13, baseline: baseline, recent: recent)
        let evaluation = CareEvaluator.evaluate(snapshots: snapshots, grantedScopes: []) // 全部撤回
        XCTAssertFalse(evaluation.shouldNotify)
    }

    func testCareDisabled_neverNotifies() {
        var recent = baseline
        recent.sleepHours = 5.5
        recent.steps = 4000
        let snapshots = makeSnapshots(days: 13, baseline: baseline, recent: recent)
        let evaluation = CareEvaluator.evaluate(snapshots: snapshots, grantedScopes: allScopes, careEnabled: false)
        XCTAssertFalse(evaluation.shouldNotify)
    }
}
