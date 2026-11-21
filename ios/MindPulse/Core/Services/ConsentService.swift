import Foundation
import SwiftData

/// HealthKit 数据类别与用户的同意状态。
///
/// 边界：任何读取都必须经过 ConsentService.isAllowed()；
/// 撤销授权后立即停止读取与上传，已有服务端数据通过"删除数据"清空。
enum HealthScope: String, CaseIterable, Identifiable {
    case sleep
    case restingHeartRate = "resting_heart_rate"
    case hrv
    case steps

    var id: String { rawValue }

    var serverScope: String { "healthkit.\(rawValue)" }

    var title: String {
        switch self {
        case .sleep: return "睡眠时长"
        case .restingHeartRate: return "静息心率"
        case .hrv: return "心率变异性 (HRV)"
        case .steps: return "步数"
        }
    }

    var whyNeeded: String {
        switch self {
        case .sleep: return "帮助你回顾自己最近一段时间的睡眠节奏，作为自我参考的趋势。"
        case .restingHeartRate: return "帮助你观察身体负荷的变化趋势，仅作参考。"
        case .hrv: return "帮助你观察身体恢复状态的整体趋势，仅作参考。"
        case .steps: return "帮助你观察日常活动量的变化趋势，仅作参考。"
        }
    }

    var neverUsedFor: String {
        "不会用于诊断任何疾病，不会生成\"抑郁指数\"或\"焦虑指数\"之类的分数，也不会上传原始逐分钟数据。"
    }
}

@MainActor
final class ConsentService: ObservableObject {
    @Published private(set) var grantedScopes: Set<HealthScope> = []

    private let context: ModelContext
    private let api: ChatAPI

    init(context: ModelContext, api: ChatAPI) {
        self.context = context
        self.api = api
    }

    func load() {
        let descriptor = FetchDescriptor<ConsentRecordModel>(
            predicate: #Predicate { $0.granted == true && $0.revokedAt == nil }
        )
        let records = (try? context.fetch(descriptor)) ?? []
        let scopes = Set(records.map(\.scope))
        grantedScopes = Set(HealthScope.allCases.filter { scopes.contains($0.serverScope) })
    }

    func isAllowed(_ scope: HealthScope) -> Bool {
        grantedScopes.contains(scope)
    }

    func grant(_ scope: HealthScope) {
        context.insert(ConsentRecordModel(scope: scope.serverScope, granted: true))
        try? context.save()
        grantedScopes.insert(scope)
        syncServer(scope: scope, granted: true)
    }

    func revoke(_ scope: HealthScope) {
        let serverScope = scope.serverScope
        let descriptor = FetchDescriptor<ConsentRecordModel>(
            predicate: #Predicate { $0.scope == serverScope && $0.granted == true && $0.revokedAt == nil }
        )
        for record in (try? context.fetch(descriptor)) ?? [] {
            record.revokedAt = Date()
        }
        try? context.save()
        grantedScopes.remove(scope)
        syncServer(scope: scope, granted: false)
    }

    func revokeAll() {
        for scope in HealthScope.allCases {
            revoke(scope)
        }
    }

    private func syncServer(scope: HealthScope, granted: Bool) {
        // 同意状态同步到服务端（尽力而为；本地记录是权威来源）
        Task { [api] in
            _ = try? await api.setConsent(scope: scope.serverScope, granted: granted)
        }
    }
}
