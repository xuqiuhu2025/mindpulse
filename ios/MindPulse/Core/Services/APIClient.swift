import Foundation

// MARK: - 聊天接口抽象（测试可注入 Mock）

protocol ChatAPI: Sendable {
    func sendChat(_ request: ChatRequestDTO) async throws -> ChatResponseDTO
    func clearChat(_ conversationId: String?) async throws -> Int
    func fetchCrisisResources(country: String?) async throws -> CrisisInfoDTO
    func fetchCareSuggestion() async throws -> CareSuggestionDTO
    func dismissCare(scope: String) async throws
    func setConsent(scope: String, granted: Bool) async throws
    func purgeServerData() async throws -> DeleteResultDTO
}

// MARK: - HTTP 客户端

/// 服务器 API 客户端。
///
/// 安全约定：
/// - 永远不携带 Authorization 头——LLM API key 只存在于服务端环境变量，
///   客户端没有任何密钥（有单元测试断言这一点）。
/// - 除本地回环（127.0.0.1/localhost）外强制 HTTPS。
final class APIClient: ChatAPI, @unchecked Sendable {
    enum APIError: LocalizedError {
        case insecureTransport
        case badStatus(Int)

        var errorDescription: String? {
            switch self {
            case .insecureTransport:
                return "只允许 HTTPS 连接（本地开发环境除外）。请在设置中使用 https:// 服务器地址。"
            case .badStatus(let code):
                return "服务器返回错误（\(code)）"
            }
        }
    }

    var serverURL: URL
    let deviceID: String
    private let session: URLSession

    /// 仅供测试观察请求头
    private(set) var lastRequestHeaders: [String: String] = [:]

    init(serverURL: URL, deviceID: String, session: URLSession = .shared) {
        self.serverURL = serverURL
        self.deviceID = deviceID
        self.session = session
    }

    // MARK: 请求构造

    func makeRequest(path: String, method: String, body: Data? = nil) throws -> URLRequest {
        guard var components = URLComponents(url: serverURL, resolvingAgainstBaseURL: false) else {
            throw APIError.insecureTransport
        }
        components.path = path
        guard let url = components.url else { throw APIError.insecureTransport }

        let scheme = url.scheme?.lowercased() ?? ""
        let host = url.host ?? ""
        let isLoopback = host == "127.0.0.1" || host == "localhost" || host == "::1"
        if scheme != "https" && !isLoopback {
            throw APIError.insecureTransport
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.httpBody = body
        request.timeoutInterval = 30
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue(deviceID, forHTTPHeaderField: "X-Device-ID")
        // 注意：刻意不设置 Authorization。任何密钥都不应出现在客户端。
        lastRequestHeaders = request.allHTTPHeaderFields ?? [:]
        return request
    }

    private func encode<T: Encodable>(_ value: T) throws -> Data {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return try encoder.encode(value)
    }

    private func decode<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(type, from: data)
    }

    func send<T: Decodable>(_ type: T.Type, request: URLRequest) async throws -> T {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.badStatus(-1) }
        guard (200..<300).contains(http.statusCode) else { throw APIError.badStatus(http.statusCode) }
        return try decode(type, from: data)
    }

    // MARK: ChatAPI

    func sendChat(_ chatRequest: ChatRequestDTO) async throws -> ChatResponseDTO {
        let request = try makeRequest(
            path: "/api/chat",
            method: "POST",
            body: try encode(chatRequest)
        )
        return try await send(ChatResponseDTO.self, request: request)
    }

    func clearChat(_ conversationId: String?) async throws -> Int {
        let body = try encode(["conversation_id": conversationId])
        let request = try makeRequest(path: "/api/chat/clear", method: "POST", body: body)
        let result = try await send([String: Int].self, request: request)
        return result["cleared_messages"] ?? 0
    }

    func fetchCrisisResources(country: String?) async throws -> CrisisInfoDTO {
        var path = "/api/crisis/resources"
        if let country, !country.isEmpty {
            path += "?country=\(country)"
        }
        let request = try makeRequest(path: path, method: "GET")
        return try await send(CrisisInfoDTO.self, request: request)
    }

    func fetchCareSuggestion() async throws -> CareSuggestionDTO {
        let request = try makeRequest(path: "/api/care/suggestions", method: "GET")
        return try await send(CareSuggestionDTO.self, request: request)
    }

    func dismissCare(scope: String) async throws {
        let body = try encode(["scope": scope])
        let request = try makeRequest(path: "/api/care/dismiss", method: "POST", body: body)
        _ = try await send(CareSettingsDTO.self, request: request)
    }

    func setConsent(scope: String, granted: Bool) async throws {
        let body = try encode(["scope": scope, "granted": granted])
        let request = try makeRequest(path: "/api/consent", method: "POST", body: body)
        _ = try await send(ConsentRecordDTO.self, request: request)
    }

    func purgeServerData() async throws -> DeleteResultDTO {
        let request = try makeRequest(path: "/api/data/all", method: "DELETE")
        return try await send(DeleteResultDTO.self, request: request)
    }
}
