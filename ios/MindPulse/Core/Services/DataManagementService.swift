import Foundation
import SwiftData

/// 数据管理：导出（JSON 文件）、本地彻底删除、服务端数据清除。
@MainActor
final class DataManagementService: ObservableObject {
    private let context: ModelContext
    private let api: ChatAPI

    init(context: ModelContext, api: ChatAPI) {
        self.context = context
        self.api = api
    }

    // MARK: - 导出

    func exportAllData() throws -> URL {
        func json(_ value: Double?) -> Any { value ?? NSNull() }
        func json(_ value: Int?) -> Any { value ?? NSNull() }

        var payload: [String: Any] = [
            "exported_at": ISO8601DateFormatter().string(from: Date()),
            "format_version": "1",
        ]

        let convs = try context.fetch(FetchDescriptor<ConversationModel>())
        var convList: [[String: Any]] = []
        for conv in convs {
            let msgs = try context.fetch(FetchDescriptor<MessageModel>(
                predicate: #Predicate { $0.conversationID == conv.id },
                sortBy: [SortDescriptor(\.createdAt, order: .forward)]
            ))
            convList.append([
                "id": conv.id,
                "created_at": ISO8601DateFormatter().string(from: conv.createdAt),
                "messages": msgs.map { [
                    "role": $0.role,
                    "content": $0.content,
                    "safety_level": $0.safetyLevel,
                    "created_at": ISO8601DateFormatter().string(from: $0.createdAt),
                ] },
            ])
        }
        payload["conversations"] = convList

        let moods = try context.fetch(FetchDescriptor<MoodEntryModel>())
        payload["mood_entries"] = moods.map { [
            "score": $0.score,
            "tags": $0.tags,
            "note": $0.note,
            "recorded_at": ISO8601DateFormatter().string(from: $0.recordedAt),
        ] }

        let snapshots = try context.fetch(FetchDescriptor<HealthSnapshotModel>())
        payload["health_snapshots"] = snapshots.map { [
            "date": $0.date,
            "sleep_hours": json($0.sleepHours),
            "resting_hr": json($0.restingHR),
            "hrv_sdnn": json($0.hrvSDNN),
            "steps": json($0.steps),
        ] }

        let consents = try context.fetch(FetchDescriptor<ConsentRecordModel>())
        payload["consent_records"] = consents.map { [
            "scope": $0.scope,
            "granted": $0.granted,
            "policy_version": $0.policyVersion,
        ] }

        let events = try context.fetch(FetchDescriptor<SafetyEventModel>())
        payload["safety_events"] = events.map { [
            "level": $0.level,
            "signal_categories": $0.signalCategories,
            "created_at": ISO8601DateFormatter().string(from: $0.createdAt),
        ] }

        let data = try JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted, .sortedKeys])
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("mindpulse-export-\(Int(Date().timeIntervalSince1970)).json")
        try data.write(to: url, options: .atomic)
        return url
    }

    // MARK: - 删除

    func deleteAllLocalData() throws {
        for type in [
            MessageModel.self,
            ConversationModel.self,
            MoodEntryModel.self,
            HealthSnapshotModel.self,
            ConsentRecordModel.self,
            SafetyEventModel.self,
            AppPreferencesModel.self,
        ] {
            let rows = try context.fetch(FetchDescriptor(type))
            for row in rows {
                context.delete(row)
            }
        }
        try context.save()
    }

    func purgeServerData() async throws {
        _ = try await api.purgeServerData()
    }
}
