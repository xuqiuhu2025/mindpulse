import XCTest
import SwiftData
@testable import MindPulse

/// 场景 9（客户端侧）：删除全部数据后不可继续读取。
@MainActor
final class DataDeletionTests: XCTestCase {
    func testDeleteAllLocalData_thenNothingReadable() throws {
        let container = try TestSupport.makeInMemoryContainer()
        let context = container.mainContext
        let api = MockChatAPI(response: MockChatAPI.safeResponse())
        let service = DataManagementService(context: context, api: api)

        // 写入各类数据
        let conversation = ConversationModel(id: "conv-del")
        context.insert(conversation)
        context.insert(MessageModel(conversationID: "conv-del", role: "user", content: "删除前的消息"))
        context.insert(MessageModel(conversationID: "conv-del", role: "assistant", content: "删除前的回复"))
        context.insert(MoodEntryModel(score: 5, tags: ["压力"], note: "有点累"))
        context.insert(HealthSnapshotModel(date: "2026-11-21", sleepHours: 7.5))
        context.insert(ConsentRecordModel(scope: "healthkit.sleep", granted: true))
        context.insert(SafetyEventModel(level: "support", signalCategories: ["persistent_low_mood"]))
        try context.save()

        try service.deleteAllLocalData()

        XCTAssertFalse(try context.fetch(FetchDescriptor<MessageModel>()).contains { $0.conversationID == "conv-del" })
        XCTAssertTrue(try context.fetch(FetchDescriptor<MoodEntryModel>()).isEmpty)
        XCTAssertTrue(try context.fetch(FetchDescriptor<HealthSnapshotModel>()).isEmpty)
        XCTAssertTrue(try context.fetch(FetchDescriptor<ConsentRecordModel>()).isEmpty)
        XCTAssertTrue(try context.fetch(FetchDescriptor<SafetyEventModel>()).isEmpty)
        XCTAssertTrue(try context.fetch(FetchDescriptor<ConversationModel>()).isEmpty)
    }

    func testExportProducesReadableJSON() throws {
        let container = try TestSupport.makeInMemoryContainer()
        let context = container.mainContext
        let api = MockChatAPI(response: MockChatAPI.safeResponse())
        let service = DataManagementService(context: context, api: api)

        context.insert(MoodEntryModel(score: 7, tags: ["工作"], note: "还行"))
        try context.save()

        let url = try service.exportAllData()
        let data = try Data(contentsOf: url)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        XCTAssertNotNil(json)
        XCTAssertEqual(json?["format_version"] as? String, "1")
        let moods = json?["mood_entries"] as? [[String: Any]]
        XCTAssertEqual(moods?.count, 1)
    }
}
