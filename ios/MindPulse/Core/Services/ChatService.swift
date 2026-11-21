import Foundation
import SwiftData

/// 聊天服务：本地持久化 + 服务端 LLM 对话。
/// urgent 回复由服务端 SafetyGuard 生成，客户端只负责醒目展示危机资源。
@MainActor
final class ChatService: ObservableObject {
    @Published private(set) var messages: [ChatMessage] = []
    @Published var isThinking = false
    @Published private(set) var activeCrisis: CrisisInfoDTO?
    @Published private(set) var offlineNotice: String?

    private let context: ModelContext
    private let api: ChatAPI
    private let deviceID: String
    private let country: String?
    private(set) var conversationID: String?

    static let starterPrompts = ["我今天压力很大", "我想整理一下思绪", "我只是想找个人聊聊"]

    init(context: ModelContext, api: ChatAPI, deviceID: String, country: String?) {
        self.context = context
        self.api = api
        self.deviceID = deviceID
        self.country = country
        loadLatestConversation()
    }

    // MARK: - 开场白

    func greeting() -> String {
        let hour = Calendar.current.component(.hour, from: Date())
        let partOfDay: String
        switch hour {
        case 5..<12: partOfDay = "上午好"
        case 12..<18: partOfDay = "下午好"
        default: partOfDay = "晚上好"
        }
        return "\(partOfDay)。今天过得怎么样？"
    }

    // MARK: - 发送

    func send(_ text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        offlineNotice = nil
        messages.append(ChatMessage(role: .user, text: trimmed))
        isThinking = true
        defer { isThinking = false }

        persistLocal(role: ChatMessage.Role.user.rawValue, content: trimmed, level: nil)

        do {
            let request = ChatRequestDTO(
                message: trimmed,
                conversationId: conversationID,
                country: country,
                locale: "zh"
            )
            let response = try await api.sendChat(request)
            conversationID = response.conversationId
            messages.append(
                ChatMessage(role: .assistant, text: response.reply, safetyLevel: response.safety.level)
            )
            persistLocal(role: ChatMessage.Role.assistant.rawValue, content: response.reply, level: response.safety.level)

            if response.safety.level == "urgent" {
                activeCrisis = response.safety.crisis
            }
        } catch {
            // 绝不假装 LLM 在线：如实告知离线状态
            offlineNotice = "暂时没能连接到服务。你的消息已保存在本机，稍后可以再试；如果此刻需要支持，请联系身边可信任的人。"
        }
    }

    // MARK: - 本地持久化

    private func persistLocal(role: String, content: String, level: String?) {
        let conversation = currentConversation()
        context.insert(MessageModel(
            conversationID: conversation.id,
            role: role,
            content: content,
            safetyLevel: level ?? "safe"
        ))
        conversation.updatedAt = .now
        try? context.save()
    }

    private func currentConversation() -> ConversationModel {
        let id = conversationID ?? UUID().uuidString
        let descriptor = FetchDescriptor<ConversationModel>(
            predicate: #Predicate { $0.id == id }
        )
        if let existing = (try? context.fetch(descriptor))?.first {
            return existing
        }
        let created = ConversationModel(id: id)
        context.insert(created)
        return created
    }

    private func loadLatestConversation() {
        let descriptor = FetchDescriptor<ConversationModel>(
            sortBy: [SortDescriptor(\.updatedAt, order: .reverse)]
        )
        guard let latest = (try? context.fetch(descriptor))?.first else { return }
        conversationID = latest.id
        let messageDescriptor = FetchDescriptor<MessageModel>(
            predicate: #Predicate { $0.conversationID == latest.id },
            sortBy: [SortDescriptor(\.createdAt, order: .forward)]
        )
        let rows = (try? context.fetch(messageDescriptor)) ?? []
        messages = rows.compactMap { row in
            guard let role = ChatMessage.Role(rawValue: row.role) else { return nil }
            return ChatMessage(
                id: UUID(uuidString: row.id) ?? UUID(),
                role: role,
                text: row.content,
                safetyLevel: row.safetyLevel
            )
        }
    }

    // MARK: - 清空当前对话

    func clearCurrentConversation() {
        guard let id = conversationID else { return }
        let descriptor = FetchDescriptor<MessageModel>(
            predicate: #Predicate { $0.conversationID == id }
        )
        let rows = (try? context.fetch(descriptor)) ?? []
        for row in rows {
            context.delete(row)
        }
        try? context.save()
        messages = []
        Task { try? await api.clearChat(id) }
    }
}
