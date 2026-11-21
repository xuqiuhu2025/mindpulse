import Foundation
import SwiftData

// MARK: - SwiftData 本地模型（本地优先：所有用户数据默认只存在设备上）

@Model
final class ConversationModel {
    var id: String
    var createdAt: Date
    var updatedAt: Date

    init(id: String = UUID().uuidString, createdAt: Date = .now, updatedAt: Date = .now) {
        self.id = id
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
}

@Model
final class MessageModel {
    var id: String
    var conversationID: String
    var role: String // user | assistant
    var content: String
    var safetyLevel: String
    var createdAt: Date

    init(id: String = UUID().uuidString, conversationID: String, role: String, content: String, safetyLevel: String = "safe", createdAt: Date = .now) {
        self.id = id
        self.conversationID = conversationID
        self.role = role
        self.content = content
        self.safetyLevel = safetyLevel
        self.createdAt = createdAt
    }
}

@Model
final class MoodEntryModel {
    var id: String
    var score: Int // 1-10，用户主动填写
    var tags: [String]
    var note: String
    var safetyLevel: String
    var recordedAt: Date

    init(id: String = UUID().uuidString, score: Int, tags: [String] = [], note: String = "", safetyLevel: String = "safe", recordedAt: Date = .now) {
        self.id = id
        self.score = score
        self.tags = tags
        self.note = note
        self.safetyLevel = safetyLevel
        self.recordedAt = recordedAt
    }
}

@Model
final class ConsentRecordModel {
    var id: String
    var scope: String
    var granted: Bool
    var policyVersion: String
    var grantedAt: Date
    var revokedAt: Date?

    init(id: String = UUID().uuidString, scope: String, granted: Bool, policyVersion: String = "v1", grantedAt: Date = .now, revokedAt: Date? = nil) {
        self.id = id
        self.scope = scope
        self.granted = granted
        self.policyVersion = policyVersion
        self.grantedAt = grantedAt
        self.revokedAt = revokedAt
    }
}

@Model
final class HealthSnapshotModel {
    var id: String
    var date: String // YYYY-MM-DD
    var sleepHours: Double?
    var restingHR: Double?
    var hrvSDNN: Double?
    var steps: Int?
    var source: String

    init(id: String = UUID().uuidString, date: String, sleepHours: Double? = nil, restingHR: Double? = nil, hrvSDNN: Double? = nil, steps: Int? = nil, source: String = "apple_healthkit") {
        self.id = id
        self.date = date
        self.sleepHours = sleepHours
        self.restingHR = restingHR
        self.hrvSDNN = hrvSDNN
        self.steps = steps
        self.source = source
    }
}

@Model
final class SafetyEventModel {
    var id: String
    var level: String
    var signalCategories: [String]
    var promptInjection: Bool
    var createdAt: Date

    init(id: String = UUID().uuidString, level: String, signalCategories: [String] = [], promptInjection: Bool = false, createdAt: Date = .now) {
        self.id = id
        self.level = level
        self.signalCategories = signalCategories
        self.promptInjection = promptInjection
        self.createdAt = createdAt
    }
}

@Model
final class AppPreferencesModel {
    var deviceID: String
    var careEnabled: Bool
    var careFrequency: String
    var country: String
    var serverURL: String
    var updatedAt: Date

    init(deviceID: String, careEnabled: Bool = true, careFrequency: String = "standard", country: String = "", serverURL: String = "", updatedAt: Date = .now) {
        self.deviceID = deviceID
        self.careEnabled = careEnabled
        self.careFrequency = careFrequency
        self.country = country
        self.serverURL = serverURL
        self.updatedAt = updatedAt
    }
}
