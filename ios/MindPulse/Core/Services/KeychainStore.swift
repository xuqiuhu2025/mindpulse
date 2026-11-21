import Foundation
import Security

/// Keychain 封装：只存本地敏感配置（设备 UUID 等），绝不存任何服务器 API key——
/// MindPulse 客户端不需要也不应该持有 LLM 密钥。
struct KeychainStore {
    private let service: String

    init(service: String = "org.mindpulse.app") {
        self.service = service
    }

    func read(_ account: String) -> String? {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    @discardableResult
    func save(_ value: String, account: String) -> Bool {
        let data = value.data(using: .utf8) ?? Data()
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        let attributes: [String: Any] = [kSecValueData as String: data]
        var status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            var createQuery = query
            createQuery[kSecValueData as String] = data
            status = SecItemAdd(createQuery as CFDictionary, nil)
        }
        return status == errSecSuccess
    }

    @discardableResult
    func delete(_ account: String) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        return SecItemDelete(query as CFDictionary) == errSecSuccess
    }
}
