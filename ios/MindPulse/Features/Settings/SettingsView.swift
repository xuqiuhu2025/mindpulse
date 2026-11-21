import SwiftUI
import SwiftData

/// 设置页：主动关心开关、HealthKit 撤销入口、导出/删除数据、关于与免责声明。
struct SettingsView: View {
    @EnvironmentObject private var environment: AppEnvironment
    @EnvironmentObject private var consent: ConsentService
    @Environment(\.modelContext) private var modelContext
    @Environment(\.openURL) private var openURL

    @State private var confirmDelete = false
    @State private var statusMessage: String?
    @State private var exportURL: URL?

    var body: some View {
        Form {
            careSection
            healthSection
            dataSection
            aboutSection
        }
        .navigationTitle("设置")
        .alert("删除全部数据？", isPresented: $confirmDelete) {
            Button("取消", role: .cancel) {}
            Button("全部删除", role: .destructive) { deleteAll() }
        } message: {
            Text("将删除本机上的聊天、心情记录、健康聚合数据与同意记录。此操作不可恢复。")
        }
        .sheet(isPresented: Binding(
            get: { exportURL != nil },
            set: { if !$0 { exportURL = nil } }
        )) {
            if let exportURL {
                ShareLink(item: exportURL) {
                    Text("分享导出文件")
                }
            }
        }
    }

    // MARK: 主动关心

    private var careSection: some View {
        Section("主动关心") {
            Toggle("接收主动关心", isOn: Binding(
                get: { environment.preferences.preferences?.careEnabled ?? true },
                set: { enabled in
                    environment.preferences.update { $0.careEnabled = enabled; $0.careFrequency = enabled ? "standard" : "off" }
                }
            ))
            if environment.preferences.preferences?.careEnabled == true {
                Picker("提醒频率", selection: Binding(
                    get: { environment.preferences.preferences?.careFrequency ?? "standard" },
                    set: { frequency in environment.preferences.update { $0.careFrequency = frequency } }
                )) {
                    Text("标准").tag("standard")
                    Text("减少").tag("reduced")
                }
                .pickerStyle(.segmented)
            }
            Text("当已授权的多项健康趋势同时变化，或某项变化持续一段时间时，MindPulse 可能温和地问问你的状态。这些提示只是观察，不是医学判断。")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
    }

    // MARK: 健康数据

    private var healthSection: some View {
        Section("健康数据 (HealthKit)") {
            ForEach(HealthScope.allCases) { scope in
                Toggle(scope.title, isOn: Binding(
                    get: { consent.isAllowed(scope) },
                    set: { allowed in
                        if allowed {
                            consent.grant(scope)
                        } else {
                            consent.revoke(scope)
                        }
                    }
                ))
            }
            Text("关闭后 MindPulse 立即停止读取与上传对应数据。你也可以在 iOS 系统设置 → 隐私与安全性 → 健康中管理权限。")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
    }

    // MARK: 数据与隐私

    private var dataSection: some View {
        Section("数据与隐私") {
            Button {
                exportData()
            } label: {
                Label("导出我的数据 (JSON)", systemImage: "square.and.arrow.up")
            }

            Button(role: .destructive) {
                environment.chat.clearCurrentConversation()
                statusMessage = "当前对话已清空。"
            } label: {
                Label("清空当前对话", systemImage: "eraser")
            }

            Button(role: .destructive) {
                confirmDelete = true
            } label: {
                Label("删除全部数据（本机）", systemImage: "trash")
            }

            Button(role: .destructive) {
                Task { await purgeServer() }
            } label: {
                Label("清除服务器上的数据", systemImage: "cloud.slash")
            }

            if let statusMessage {
                Text(statusMessage)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
    }

    // MARK: 关于

    private var aboutSection: some View {
        Section("关于") {
            Text(Strings.notMedicalAdvice)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(Strings.disclaimer)
                .font(.caption2)
                .foregroundStyle(.secondary)

            LabeledContent("服务器地址") {
                TextField("https://…", text: Binding(
                    get: { environment.serverURL.absoluteString },
                    set: { if let url = URL(string: $0.trimmingCharacters(in: .whitespaces)) { environment.serverURL = url } }
                ))
                .font(.caption)
                .keyboardType(.URL)
                .autocorrectionDisabled()
            }

            Button {
                if let url = URL(string: Strings.repoURL) {
                    openURL(url)
                }
            } label: {
                Label("开源仓库 (GitHub)", systemImage: "link")
            }

            LabeledContent("版本", value: "0.1.0")
            LabeledContent("设备标识（伪匿名）", value: environment.deviceID)
                .font(.caption)
        }
    }

    // MARK: 动作

    private func exportData() {
        do {
            exportURL = try environment.dataManagement.exportAllData()
            statusMessage = "已生成导出文件，请通过分享面板保存。"
        } catch {
            statusMessage = "导出失败：\(error.localizedDescription)"
        }
    }

    private func deleteAll() {
        do {
            try environment.dataManagement.deleteAllLocalData()
            environment.consent.load()
            statusMessage = "本机全部数据已删除。"
        } catch {
            statusMessage = "删除失败：\(error.localizedDescription)"
        }
    }

    private func purgeServer() async {
        do {
            try await environment.dataManagement.purgeServerData()
            statusMessage = "服务器上的数据已清除。"
        } catch {
            statusMessage = "清除失败：\(error.localizedDescription)"
        }
    }
}
