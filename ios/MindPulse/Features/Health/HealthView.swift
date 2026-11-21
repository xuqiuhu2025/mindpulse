import SwiftUI
import SwiftData

/// 健康页：首次使用展示清晰的授权说明页；授权后展示聚合趋势与主动关心卡片。
struct HealthView: View {
    @EnvironmentObject private var environment: AppEnvironment
    @EnvironmentObject private var consent: ConsentService
    @EnvironmentObject private var healthKit: HealthKitService
    @EnvironmentObject private var care: CareCenter
    @Environment(\.modelContext) private var modelContext

    @State private var syncing = false
    @State private var syncMessage: String?
    @Query(sort: [SortDescriptor(\HealthSnapshotModel.date, order: .forward)])
    private var snapshots: [HealthSnapshotModel]

    var body: some View {
        Group {
            if !healthKit.isAvailable {
                unsupportedView
            } else if consent.grantedScopes.isEmpty {
                HealthConsentIntro(
                    healthKit: healthKit,
                    consent: consent,
                    onCompleted: { Task { await syncNow(showingMessage: true) } }
                )
            } else {
                dashboard
            }
        }
        .background(Theme.background)
        .navigationTitle("健康")
        .task {
            if !consent.grantedScopes.isEmpty {
                await care.refresh(
                    grantedScopes: consent.grantedScopes,
                    careEnabled: environment.preferences.preferences?.careEnabled ?? true
                )
            }
        }
    }

    private var unsupportedView: some View {
        VStack(spacing: 12) {
            Image(systemName: "heart.slash")
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text("这台设备不支持健康数据")
                .font(.headline)
            Text("MindPulse 在没有健康数据的情况下依然可以陪你聊天、记录心情。")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(24)
    }

    private var dashboard: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                if let suggestion = care.suggestion, suggestion.shouldNotify {
                    CareSuggestionCard(suggestion: suggestion)
                } else if let local = care.localEvaluation, local.shouldNotify, let message = local.message {
                    CareSuggestionCard(local: local, message: message)
                }

                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("聚合趋势")
                            .font(.headline)
                        Spacer()
                        Button {
                            Task { await syncNow(showingMessage: true) }
                        } label: {
                            if syncing {
                                ProgressView()
                            } else {
                                Label("同步", systemImage: "arrow.triangle.2.circlepath")
                                    .font(.footnote)
                            }
                        }
                        .disabled(syncing)
                    }

                    if let message = syncMessage {
                        Text(message)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }

                    if snapshots.count < 10 {
                        Text("数据还在积累中（需要约 \(max(0, 10 - snapshots.count)) 天）。\n在数据足够之前，MindPulse 不会生成任何趋势解读。")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(consent.grantedScopes.sorted { $0.title < $1.title }) { scope in
                            MetricSummaryRow(scope: scope, snapshots: snapshots)
                        }
                    }

                    Text(Strings.healthTrendDisclaimer)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                .cardStyle()
            }
            .padding(16)
        }
        .refreshable {
            await care.refresh(
                grantedScopes: consent.grantedScopes,
                careEnabled: environment.preferences.preferences?.careEnabled ?? true
            )
        }
    }

    private func syncNow(showingMessage: Bool) async {
        syncing = true
        defer { syncing = false }
        do {
            let rows = try await healthKit.buildSnapshots(days: 14, grantedScopes: consent.grantedScopes)
            // 本地保存聚合值
            for row in rows {
                let date = row.date
                let existing = try modelContext.fetch(FetchDescriptor<HealthSnapshotModel>(
                    predicate: #Predicate { $0.date == date }
                )).first
                let model = existing ?? HealthSnapshotModel(date: row.date)
                model.sleepHours = row.sleepHours
                model.restingHR = row.restingHR
                model.hrvSDNN = row.hrvSDNN
                model.steps = row.steps
                if existing == nil {
                    modelContext.insert(model)
                }
            }
            try modelContext.save()

            // 上传聚合值到服务端（仅聚合，逐分钟数据不出设备）
            let payloads: [[String: Any?]] = rows.map {
                ["date": $0.date, "sleep_hours": $0.sleepHours, "resting_hr": $0.restingHR, "hrv_sdnn": $0.hrvSDNN, "steps": $0.steps]
            }
            if let data = try? JSONSerialization.data(withJSONObject: payloads),
               let request = try? environment.api.makeRequest(path: "/api/health/snapshots", method: "POST", body: data) {
                _ = try? await URLSession.shared.data(for: request)
            }

            if showingMessage {
                syncMessage = rows.isEmpty ? "暂无健康数据（设备可能尚未连接或没有记录）。" : "已同步 \(rows.count) 天的聚合数据。"
            }
            await care.refresh(
                grantedScopes: consent.grantedScopes,
                careEnabled: environment.preferences.preferences?.careEnabled ?? true
            )
        } catch {
            syncMessage = "同步失败：\(error.localizedDescription)"
        }
    }
}

// MARK: - 指标摘要行（中性描述）

struct MetricSummaryRow: View {
    let scope: HealthScope
    let snapshots: [HealthSnapshotModel]

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(scope.title)
                .font(.subheadline)
                .fontWeight(.medium)
            Text(description)
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
    }

    private var description: String {
        let values: [Double]
        switch scope {
        case .sleep: values = snapshots.compactMap(\.sleepHours)
        case .restingHeartRate: values = snapshots.compactMap(\.restingHR)
        case .hrv: values = snapshots.compactMap(\.hrvSDNN)
        case .steps: values = snapshots.compactMap { $0.steps.map(Double.init) }
        }

        guard values.count >= 10 else { return "数据积累中" }
        let baseline = values.dropLast(3)
        let recent = values.suffix(3)
        guard let baselineAvg = baseline.isEmpty ? nil : baseline.reduce(0, +) / Double(baseline.count),
              let recentAvg = recent.isEmpty ? nil : recent.reduce(0, +) / Double(recent.count)
        else { return "数据积累中" }

        let unit: String
        switch scope {
        case .sleep: unit = "小时"
        case .restingHeartRate: unit = "次/分"
        case .hrv: unit = "毫秒"
        case .steps: unit = "步"
        }

        let diff = recentAvg - baselineAvg
        let direction = abs(diff) < 0.01 ? "接近" : (diff > 0 ? "高于" : "低于")
        return String(
            format: "近 3 天平均比之前的基线%@约 %.1f %@（自我参考，非医学结论）",
            direction, abs(diff), unit
        )
    }
}

// MARK: - 授权说明页

struct HealthConsentIntro: View {
    let healthKit: HealthKitService
    let consent: ConsentService
    let onCompleted: () -> Void

    @State private var isRequesting = false
    @State private var failureMessage: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("关于健康数据，你想知道的")
                    .font(.title2)
                    .fontWeight(.semibold)

                Text("MindPulse 可以在你明确同意后，读取以下数据的每日汇总，帮你回顾最近的生活节奏。这一步完全由你决定，也可以随时撤销。")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                ForEach(HealthScope.allCases) { scope in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(scope.title)
                            .font(.subheadline)
                            .fontWeight(.semibold)
                        Text("为什么需要：\(scope.whyNeeded)")
                            .font(.footnote)
                        Text("不会用于：\(scope.neverUsedFor)")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                    .cardStyle()
                }

                Button {
                    Task { await request() }
                } label: {
                    if isRequesting {
                        ProgressView()
                            .frame(maxWidth: .infinity)
                    } else {
                        Text("我了解并同意，开始授权")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 6)
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(isRequesting)

                if let failureMessage {
                    Text(failureMessage)
                        .font(.footnote)
                        .foregroundStyle(Theme.urgent)
                }

                Text("你随时可以在\"设置 → 健康数据\"中撤销授权，或在系统设置中管理权限。MindPulse 不会在后台读取你的健康数据。")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .padding(16)
        }
    }

    private func request() async {
        isRequesting = true
        defer { isRequesting = false }
        let granted = (try? await healthKit.requestAuthorization()) ?? false
        if granted {
            for scope in HealthScope.allCases {
                consent.grant(scope)
            }
            onCompleted()
        } else {
            failureMessage = "未获得授权或设备不支持。你仍然可以使用 MindPulse 的聊天与心情记录功能。"
        }
    }
}
