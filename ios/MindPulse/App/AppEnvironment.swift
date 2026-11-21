import Foundation
import SwiftUI
import SwiftData

/// 应用级服务容器。所有服务都在这里创建并注入视图。
@MainActor
final class AppEnvironment: ObservableObject {
    let container: ModelContainer
    let preferences: PreferencesStore
    let api: APIClient
    let chat: ChatService
    let healthKit: HealthKitService
    let consent: ConsentService
    let care: CareCenter
    let dataManagement: DataManagementService

    init(container: ModelContainer) {
        self.container = container
        let context = container.mainContext
        self.preferences = PreferencesStore(context: context)
        let deviceID = DeviceIdentity.getOrCreate()

        // 服务器地址：默认本地开发环境，可在设置中改为 https 服务器。
        let serverURL = Self.loadServerURL(preferences: preferences)
        self.api = APIClient(serverURL: serverURL, deviceID: deviceID)

        self.healthKit = HealthKitService()
        self.consent = ConsentService(context: context, api: api)
        self.chat = ChatService(context: context, api: api, deviceID: deviceID, country: preferences.preferences?.country)
        self.care = CareCenter(context: context, api: api)
        self.dataManagement = DataManagementService(context: context, api: api)

        self.consent.load()
        self.preferences.load()
    }

    var deviceID: String { api.deviceID }

    var serverURL: URL {
        get { api.serverURL }
        set {
            api.serverURL = newValue
            preferences.update { $0.serverURL = newValue.absoluteString }
        }
    }

    private static func loadServerURL(preferences: PreferencesStore) -> URL {
        if let stored = preferences.preferences?.serverURL, let url = URL(string: stored) {
            return url
        }
        return URL(string: "http://127.0.0.1:8000")! // 本地开发默认值
    }
}
