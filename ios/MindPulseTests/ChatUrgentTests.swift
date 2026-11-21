import XCTest
import SwiftData
@testable import MindPulse

/// 场景 4/5（客户端侧）：urgent 响应驱动危机资源展示；离线时不假装在线。
@MainActor
final class ChatUrgentTests: XCTestCase {
    func testUrgentResponse_activatesCrisisUI() async throws {
        let container = try TestSupport.makeInMemoryContainer()
        let api = MockChatAPI(response: MockChatAPI.urgentResponse(country: "CN"))
        let service = ChatService(context: container.mainContext, api: api, deviceID: "test-device-01", country: "CN")

        await service.send("我想自杀")

        XCTAssertTrue(service.messages.contains { $0.safetyLevel == "urgent" })
        XCTAssertNotNil(service.activeCrisis)
        XCTAssertEqual(service.activeCrisis?.emergencyNumber, "120")
        XCTAssertEqual(service.activeCrisis?.needCountry, false)
    }

    func testUrgentWithoutCountry_promptsRegionQuestion() async throws {
        let container = try TestSupport.makeInMemoryContainer()
        let api = MockChatAPI(response: MockChatAPI.urgentResponse(country: nil))
        let service = ChatService(context: container.mainContext, api: api, deviceID: "test-device-01", country: nil)

        await service.send("我不想活了")

        XCTAssertEqual(service.activeCrisis?.needCountry, true, "未提供国家时应先询问地区")
    }

    func testSafeResponse_noCrisis() async throws {
        let container = try TestSupport.makeInMemoryContainer()
        let api = MockChatAPI(response: MockChatAPI.safeResponse(reply: "你好呀。今天过得怎么样？"))
        let service = ChatService(context: container.mainContext, api: api, deviceID: "test-device-01", country: nil)

        await service.send("你好")

        XCTAssertNil(service.activeCrisis)
        XCTAssertEqual(service.messages.count, 2)
    }

    func testOfflineError_showsHonestNotice_notFakeReply() async throws {
        let container = try TestSupport.makeInMemoryContainer()
        let api = MockChatAPI(response: MockChatAPI.safeResponse())
        api.errorToThrow = URLError(.notConnectedToInternet)
        let service = ChatService(context: container.mainContext, api: api, deviceID: "test-device-01", country: nil)

        await service.send("在吗")

        XCTAssertNotNil(service.offlineNotice, "断网时必须如实提示，不能假装 AI 在线")
        XCTAssertTrue(service.messages.contains { $0.role == .user })
        XCTAssertFalse(service.messages.contains { $0.role == .assistant && $0.safetyLevel != nil && $0.text.contains("抱歉，我这边暂时") },
                       "不应伪造一条成功回复")
    }

    func testGreeting_isSimpleAndNatural() {
        let container = try? TestSupport.makeInMemoryContainer()
        XCTAssertNotNil(container)
        let api = MockChatAPI(response: MockChatAPI.safeResponse())
        let service = ChatService(context: container!.mainContext, api: api, deviceID: "test-device-01", country: nil)
        let greeting = service.greeting()
        XCTAssertTrue(greeting.contains("好"))
        XCTAssertTrue(greeting.contains("怎么样") || greeting.contains("聊聊"))
        // 不伪造现实动作 / 身体
        for phrase in ["我刚喝完水", "我刚出门", "我坐在你身边"] {
            XCTAssertFalse(greeting.contains(phrase))
        }
    }
}
