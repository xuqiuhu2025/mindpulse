import Foundation
import XCTest
import SwiftData

@testable import MindPulse

// MARK: - 测试工具

enum TestSupport {
    static func makeInMemoryContainer() throws -> ModelContainer {
        let config = ModelConfiguration(isStoredInMemoryOnly: true)
        return try ModelContainer(
            for: [
                ConversationModel.self,
                MessageModel.self,
                MoodEntryModel.self,
                ConsentRecordModel.self,
                HealthSnapshotModel.self,
                SafetyEventModel.self,
                AppPreferencesModel.self,
            ],
            configurations: [config]
        )
    }

    static let forbiddenDiseaseWords = ["抑郁症", "焦虑症", "可能患有", "诊断你", "depression", "diagnos"]

    static func assertNoDiseaseLanguage(_ text: String, file: StaticString = #filePath, line: UInt = #line) {
        for word in forbiddenDiseaseWords {
            XCTAssertFalse(text.contains(word), "出现疾病词汇：\(word)", file: file, line: line)
        }
    }
}

// MARK: - Mock API

final class MockChatAPI: ChatAPI, @unchecked Sendable {
    var nextResponse: ChatResponseDTO
    var errorToThrow: Error?
    private(set) var sentRequests: [ChatRequestDTO] = []
    private(set) var consentCalls: [(scope: String, granted: Bool)] = []

    init(response: ChatResponseDTO) {
        self.nextResponse = response
    }

    static func safeResponse(reply: String = "我在听，慢慢说。") -> ChatResponseDTO {
        ChatResponseDTO(
            conversationId: "conv-1",
            messageId: "m1",
            reply: reply,
            safety: SafetyInfoDTO(level: "safe", signalCategories: [], promptInjection: false, crisis: nil),
            promptVersion: "chat/v1"
        )
    }

    static func urgentResponse(country: String? = nil) -> ChatResponseDTO {
        ChatResponseDTO(
            conversationId: "conv-1",
            messageId: "m2",
            reply: "如果你现在处于立即危险中，请立即拨打当地急救服务或前往最近的急诊室。",
            safety: SafetyInfoDTO(
                level: "urgent",
                signalCategories: ["self_harm_intent"],
                promptInjection: false,
                crisis: CrisisInfoDTO(
                    showResources: true,
                    needCountry: country == nil,
                    country: country,
                    emergencyNumber: country == nil ? nil : "120",
                    resources: [],
                    directories: ["https://findahelpline.com"],
                    note: nil
                )
            ),
            promptVersion: "chat/v1"
        )
    }

    func sendChat(_ request: ChatRequestDTO) async throws -> ChatResponseDTO {
        if let error = errorToThrow { throw error }
        sentRequests.append(request)
        return nextResponse
    }

    func clearChat(_ conversationId: String?) async throws -> Int { 0 }

    func fetchCrisisResources(country: String?) async throws -> CrisisInfoDTO {
        nextResponse.safety.crisis ?? MockChatAPI.urgentResponse(country: country).safety.crisis!
    }

    func fetchCareSuggestion() async throws -> CareSuggestionDTO {
        CareSuggestionDTO(shouldNotify: false, message: nil, reasons: [], metrics: [], promptVersion: "care/v1")
    }

    func dismissCare(scope: String) async throws {}

    func setConsent(scope: String, granted: Bool) async throws {
        consentCalls.append((scope, granted))
    }

    func purgeServerData() async throws -> DeleteResultDTO {
        DeleteResultDTO(deleted: [:], message: "ok")
    }
}
