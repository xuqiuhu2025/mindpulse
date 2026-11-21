import SwiftUI
import SwiftData

@main
struct MindPulseApp: App {
    let container: ModelContainer
    @StateObject private var environment: AppEnvironment

    init() {
        do {
            container = try ModelContainer(
                for: ConversationModel.self,
                     MessageModel.self,
                     MoodEntryModel.self,
                     ConsentRecordModel.self,
                     HealthSnapshotModel.self,
                     SafetyEventModel.self,
                     AppPreferencesModel.self
            )
        } catch {
            fatalError("无法初始化本地数据库: \(error)")
        }
        _environment = StateObject(wrappedValue: AppEnvironment(container: container))
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
