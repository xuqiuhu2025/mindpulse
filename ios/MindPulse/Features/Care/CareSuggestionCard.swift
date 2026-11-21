import SwiftUI

/// 主动关心卡片：必须说明“为什么出现这条提示”，并提供忽略/关闭入口。
struct CareSuggestionCard: View {
    var suggestion: CareSuggestionDTO?
    var local: CareEvaluation? = nil
    var message: String = ""

    @EnvironmentObject private var environment: AppEnvironment
    @EnvironmentObject private var care: CareCenter
    @State private var showReasons = false
    @State private var dismissed = false

    var body: some View {
        if !dismissed {
            VStack(alignment: .leading, spacing: 12) {
                Label("温和的提醒", systemImage: "leaf")
                    .font(.footnote)
                    .fontWeight(.semibold)
                    .foregroundStyle(Theme.accent)

                Text(displayMessage)
                    .font(.subheadline)

                DisclosureGroup(isExpanded: $showReasons) {
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(reasons, id: \.self) { reason in
                            Text("· \(reason)")
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.top, 6)
                } label: {
                    Text("为什么会出现这条提示？")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                HStack {
                    Button("忽略这条") {
                        dismissed = true
                    }
                    .buttonStyle(.bordered)

                    Button("关闭此类提醒") {
                        dismissed = true
                        environment.preferences.update { prefs in
                            prefs.careEnabled = false
                            prefs.careFrequency = "off"
                        }
                        Task { try? await careDismissAll() }
                    }
                    .buttonStyle(.bordered)
                }
                .font(.footnote)

                Text("你也可以随时在“设置 → 主动关心”里调整。")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .cardStyle()
        }
    }

    private var displayMessage: String {
        suggestion?.message ?? (local?.message ?? message)
    }

    private var reasons: [String] {
        if let suggestion {
            return suggestion.reasons.map(\.detail)
        }
        return local?.reasons ?? []
    }

    private func careDismissAll() async throws {
        let client = APIClient(serverURL: environment.serverURL, deviceID: environment.deviceID)
        try await client.dismissCare(scope: "all")
    }
}
