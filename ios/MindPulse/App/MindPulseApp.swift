import SwiftUI
import SwiftData

@main
struct MindPulseApp: App {
    let container: ModelContainer
    @StateObject private var environment: AppEnvironment

    init() {
        do {
            let modelContainer = try ModelContainer(
                for: ConversationModel.self,
                     MessageModel.self,
                     MoodEntryModel.self,
                     ConsentRecordModel.self,
                     HealthSnapshotModel.self,
                     SafetyEventModel.self,
                     AppPreferencesModel.self
            )
            self.container = modelContainer
            // StateObject 的 wrappedValue 是 escaping autoclosure，
            // 只能捕获局部常量，不能捕获未初始化完的 self。
            _environment = StateObject(wrappedValue: AppEnvironment(container: modelContainer))
        } catch {
            fatalError("无法初始化本地数据库: \(error)")
        }
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(environment)
                .environmentObject(environment.chat)
                .environmentObject(environment.consent)
                .environmentObject(environment.care)
                .environmentObject(environment.healthKit)
                .tint(Theme.accent)
        }
        .modelContainer(container)
    }
}
