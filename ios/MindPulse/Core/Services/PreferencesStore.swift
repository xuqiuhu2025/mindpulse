import Foundation
import SwiftData

/// 本地偏好读写（设备上的轻量设置）。
@MainActor
final class PreferencesStore: ObservableObject {
    let context: ModelContext
    @Published private(set) var preferences: AppPreferencesModel?

    init(context: ModelContext) {
        self.context = context
    }

    func load() {
        let descriptor = FetchDescriptor<AppPreferencesModel>(
            sortBy: [SortDescriptor(\.updatedAt, order: .reverse)]
        )
        preferences = (try? context.fetch(descriptor))?.first
        if preferences == nil {
            let created = AppPreferencesModel(deviceID: DeviceIdentity.getOrCreate())
            context.insert(created)
            try? context.save()
            preferences = created
        }
    }

    func update(_ mutate: (AppPreferencesModel) -> Void) {
        guard let current = preferences else { load(); return }
        mutate(current)
        current.updatedAt = .now
        try? context.save()
    }
}
