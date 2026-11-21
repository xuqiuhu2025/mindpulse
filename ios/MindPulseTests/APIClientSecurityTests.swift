import XCTest
@testable import MindPulse

/// 场景 11（客户端侧）：客户端不持有任何 API key；非本地地址强制 HTTPS。
final class APIClientSecurityTests: XCTestCase {
    private func makeClient(serverURL: URL) -> APIClient {
        APIClient(serverURL: serverURL, deviceID: "test-device-01")
    }

    func testRejectsInsecureNonLoopbackTransport() {
        let client = makeClient(serverURL: URL(string: "http://api.example.com")!)
        XCTAssertThrowsError(try client.makeRequest(path: "/api/chat", method: "POST")) { error in
            XCTAssertEqual(error as? APIClient.APIError, APIClient.APIError.insecureTransport)
        }
    }

    func testAllowsLoopbackForLocalDevelopment() throws {
        let client = makeClient(serverURL: URL(string: "http://127.0.0.1:8000")!)
        let request = try client.makeRequest(path: "/api/chat", method: "POST")
        XCTAssertEqual(request.url?.host, "127.0.0.1")
    }

    func testRequestNeverCarriesAuthorizationHeader() throws {
        // 场景 11：API key 不得出现在客户端请求中——MindPulse 客户端根本没有密钥
        let client = makeClient(serverURL: URL(string: "https://api.mindpulse.example.com")!)
        let request = try client.makeRequest(path: "/api/chat", method: "POST", body: Data("{}".utf8))
        let headers = request.allHTTPHeaderFields ?? [:]
        XCTAssertNil(headers["Authorization"], "客户端永远不应携带 Authorization 头")
        XCTAssertFalse(client.lastRequestHeaders.contains { $0.key.lowercased() == "authorization" })
        XCTAssertEqual(headers["X-Device-ID"], "test-device-01")
    }

    func testRequestAlwaysCarriesPseudonymousDeviceID() throws {
        let client = makeClient(serverURL: URL(string: "https://api.mindpulse.example.com")!)
        let request = try client.makeRequest(path: "/api/care/suggestions", method: "GET")
        XCTAssertEqual(request.value(forHTTPHeaderField: "X-Device-ID"), "test-device-01")
    }
}
