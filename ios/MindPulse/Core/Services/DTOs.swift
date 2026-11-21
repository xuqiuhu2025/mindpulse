import Foundation

// MARK: - 服务端 API 数据传输对象（与后端 Pydantic 模型对应，snake_case 自动转换）

struct ChatRequestDTO: Codable {
    var message: String
    var conversationId: String?
    var country: String?
    var locale: String = "zh"
}

struct ChatResponseDTO: Codable {
    var conversationId: String
    var messageId: String
    var reply: String
    var safety: SafetyInfoDTO
    var promptVersion: String
}

struct SafetyInfoDTO: Codable {
    var level: String // safe | support | urgent
    var signalCategories: [String]
    var promptInjection: Bool
    var crisis: CrisisInfoDTO?
}

struct CrisisInfoDTO: Codable {
    var showResources: Bool
    var needCountry: Bool
    var country: String?
    var emergencyNumber: String?
    var resources: [CrisisResourceDTO]
    var directories: [String]
    var note: String?
}

struct CrisisResourceDTO: Codable, Identifiable {
    var name: String
    var phone: String?
    var url: String?
    var hours: String?
    var source: String?
    var verified: String?

    var id: String { name + (phone ?? "") }
}

struct CareSuggestionDTO: Codable {
    var shouldNotify: Bool
    var message: String?
    var reasons: [CareReasonDTO]
    var metrics: [String]
    var promptVersion: String
}

struct CareReasonDTO: Codable, Identifiable {
    var code: String
    var detail: String
    var id: String { code + detail }
}

struct CareSettingsDTO: Codable {
    var enabled: Bool
    var frequency: String
}

struct ConsentRecordDTO: Codable {
    var scope: String
    var granted: Bool
    var policyVersion: String
    var grantedAt: String
    var revokedAt: String?
}

struct DeleteResultDTO: Codable {
    var deleted: [String: Int]
    var message: String
}

// MARK: - 客户端本地聊天消息

struct ChatMessage: Identifiable, Equatable {
    enum Role: String { case user, assistant }
    let id: UUID
    let role: Role
    let text: String
    let safetyLevel: String?

    init(id: UUID = UUID(), role: Role, text: String, safetyLevel: String? = nil) {
        self.id = id
        self.role = role
        self.text = text
        self.safetyLevel = safetyLevel
    }
}
