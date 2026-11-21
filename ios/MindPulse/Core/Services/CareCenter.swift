import Foundation
import SwiftData

/// 主动关心中心：合并本地评估与服务端建议，提供给健康页展示。
@MainActor
final class CareCenter: ObservableObject {
    @Published var suggestion: CareSuggestionDTO?
    @Published var localEvaluation: CareEvaluation?
    @Published var isLoading = false
    @Published var lastError: String?

    private let context: ModelContext
    private let api: ChatAPI

    init(context: ModelContext, api: ChatAPI) {
        self.context = context
        self.api = api
    }

    /// 从本地 SwiftData 快照构建评估输入。
    func refresh(grantedScopes: Set<HealthScope>, careEnabled: Bool) async {
        isLoading = true
        defer { isLoading = false }

        let descriptor = FetchDescriptor<HealthSnapshotModel>(
            sortBy: [SortDescriptor(\.date, order: .forward)]
        )
        let snapshots = (try? context.fetch(descriptor)) ?? []
        let inputs = snapshots.map {
            MetricDaySnapshot(
                date: $0.date,
                sleepHours: $0.sleepHours,
                restingHR: $0.restingHR,
                hrvSDNN: $0.hrvSDNN,
                steps: $0.steps
            )
        }
        localEvaluation = CareEvaluator.evaluate(
            snapshots: inputs,
            grantedScopes: grantedScopes,
            careEnabled: careEnabled
        )

        // 服务端建议（尽力而为）
        do {
            suggestion = try await api.fetchCareSuggestion()
            lastError = nil
        } catch {
            suggestion = nil
            lastError = "服务端建议暂不可用（本地评估仍然有效）"
        }
    }
}
