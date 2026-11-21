import XCTest
import SwiftData
@testable import MindPulse

/// 场景 6（客户端侧）：撤销 HealthKit 授权立即生效；同意记录留痕。
@MainActor
final class ConsentGateTests: XCTestCase {
    func testGrantThenRevoke_updatesAllowedScopes() async throws {
        let container = try TestSupport.makeInMemoryContainer()
        let api = MockChatAPI(response: MockChatAPI.safeResponse())
        let service = ConsentService(context: container.mainContext, api: api)

        service.load()
        XCTAssertTrue(service.grantedScopes.isEmpty)

        service.grant(.sleep)
        service.grant(.hrv)
        XCTAssertTrue(service.isAllowed(.sleep))
        XCTAssertTrue(service.isAllowed(.hrv))
        XCTAssertFalse(service.isAllowed(.steps))

        service.revoke(.hrv)
        XCTAssertFalse(service.isAllowed(.hrv))
        XCTAssertTrue(service.isAllowed(.sleep))

        // 同意状态已同步到服务端（尽力而为）：同步是异步 Task，这里主动让出执行器等待
        var attempts = 0
        while attempts < 50,
              !api.consentCalls.contains(where: { !$0.granted && $0.scope == HealthScope.hrv.serverScope }) {
            await Task.yield()
            attempts += 1
        }
        XCTAssertTrue(
            api.consentCalls.contains { !$0.granted && $0.scope == HealthScope.hrv.serverScope },
            "撤销后应把同意状态同步到服务端（scope=\(HealthScope.hrv.serverScope)）"
        )
    }

    func testRevokePersistedWithTimestamp() throws {
        let container = try TestSupport.makeInMemoryContainer()
        let api = MockChatAPI(response: MockChatAPI.safeResponse())
        let service = ConsentService(context: container.mainContext, api: api)

        service.grant(.steps)
        service.revoke(.steps)

        let records = try container.mainContext.fetch(FetchDescriptor<ConsentRecordModel>())
        let granted = records.filter { $0.granted && $0.revokedAt != nil }
        XCTAssertFalse(granted.isEmpty, "撤销后原授权记录应带 revokedAt 时间戳")
        XCTAssertTrue(service.grantedScopes.isEmpty)
    }

    func testRevokeAll_clearsEverything() throws {
        let container = try TestSupport.makeInMemoryContainer()
        let api = MockChatAPI(response: MockChatAPI.safeResponse())
        let service = ConsentService(context: container.mainContext, api: api)

        for scope in HealthScope.allCases {
            service.grant(scope)
        }
        service.revokeAll()
        XCTAssertTrue(service.grantedScopes.isEmpty)
        for scope in HealthScope.allCases {
            XCTAssertFalse(service.isAllowed(scope))
        }
    }
}
