import SwiftUI

struct RootView: View {
    var body: some View {
        TabView {
            NavigationStack { ChatView() }
                .tabItem { Label("聊聊", systemImage: "bubble.left.and.bubble.right") }
            NavigationStack { MoodView() }
                .tabItem { Label("心情", systemImage: "heart.text.square") }
            NavigationStack { HealthView() }
                .tabItem { Label("健康", systemImage: "waveform.path.ecg") }
            NavigationStack { SettingsView() }
                .tabItem { Label("设置", systemImage: "gearshape") }
        }
        .background(Theme.background)
    }
}
