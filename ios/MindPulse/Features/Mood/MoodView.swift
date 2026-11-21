import SwiftUI
import SwiftData
import Charts

/// 心情记录：用户主动填写 1-10 分 + 可选标签；趋势只做中性解读。
struct MoodView: View {
    @Environment(\.modelContext) private var modelContext
    @EnvironmentObject private var environment: AppEnvironment
    @Query(sort: [SortDescriptor(\MoodEntryModel.recordedAt, order: .reverse)])
    private var entries: [MoodEntryModel]

    @State private var score = 6
    @State private var selectedTags: Set<String> = []
    @State private var note = ""
    @State private var urgentCrisis: CrisisInfoDTO?

    static let tags = ["压力", "睡眠", "工作", "人际关系", "健康", "其他"]

    var body: some View {
        VStack(spacing: 0) {
            Picker("视图", selection: $tab) {
                Text("记录").tag(0)
                Text("趋势").tag(1)
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 16)
            .padding(.top, 8)

            if tab == 0 {
                MoodLogView(
                    score: $score,
                    selectedTags: $selectedTags,
                    note: $note,
                    onSave: save
                )
            } else {
                MoodTrendView(entries: entries)
            }
        }
        .background(Theme.background)
        .navigationTitle("心情")
        .sheet(isPresented: Binding(
            get: { urgentCrisis != nil },
            set: { if !$0 { urgentCrisis = nil } }
        )) {
            if let crisis = urgentCrisis {
                CrisisResourcesSheet(crisis: crisis)
            }
        }
    }

    @State private var tab = 0

    private func save() {
        let entry = MoodEntryModel(
            score: score,
            tags: Array(selectedTags).sorted(),
            note: note.trimmingCharacters(in: .whitespacesAndNewlines)
        )
        modelContext.insert(entry)
        try? modelContext.save()
        note = ""
        selectedTags = []

        // 心情备注同样要过安全检查：包含危险表达时展示危机资源
        let text = entry.note
        if !text.isEmpty {
            Task { await checkNote(text) }
        }
    }

    private func checkNote(_ text: String) async {
        let client = APIClient(serverURL: environment.serverURL, deviceID: environment.deviceID)
        guard let response = try? await client.sendChat(ChatRequestDTO(message: text)) else { return }
        if response.safety.level == "urgent" {
            urgentCrisis = response.safety.crisis
        }
    }
}

// MARK: - 记录

struct MoodLogView: View {
    @Binding var score: Int
    @Binding var selectedTags: Set<String>
    @Binding var note: String
    let onSave: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 12) {
                    Text("现在的心情")
                        .font(.headline)
                    HStack {
                        Slider(value: Binding(
                            get: { Double(score) },
                            set: { score = Int($0.rounded()) }
                        ), in: 1...10, step: 1)
                        Text("\(score)")
                            .font(.title2)
                            .fontWeight(.semibold)
                            .foregroundStyle(Theme.accent)
                            .monospacedDigit()
                    }
                    HStack {
                        Text("1 · 很糟")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Spacer()
                        Text("10 · 很好")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
                .cardStyle()

                VStack(alignment: .leading, spacing: 12) {
                    Text("相关因素（可选）")
                        .font(.headline)
                    FlowChips(tags: MoodView.tags, selected: $selectedTags)
                }
                .cardStyle()

                VStack(alignment: .leading, spacing: 8) {
                    Text("想多说两句？（可选）")
                        .font(.headline)
                    TextField("写给自己看的话…", text: $note, axis: .vertical)
                        .lineLimit(3...6)
                        .padding(10)
                        .background(Color(.tertiarySystemGroupedBackground))
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                }
                .cardStyle()

                Button {
                    onSave()
                } label: {
                    Text("保存这条记录")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 6)
                }
                .buttonStyle(.borderedProminent)
            }
            .padding(16)
        }
    }
}

struct FlowChips: View {
    let tags: [String]
    @Binding var selected: Set<String>

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 88), spacing: 8)], spacing: 8) {
            ForEach(tags, id: \.self) { tag in
                let isSelected = selected.contains(tag)
                Button {
                    if isSelected {
                        selected.remove(tag)
                    } else {
                        selected.insert(tag)
                    }
                } label: {
                    Text(tag)
                        .font(.subheadline)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(isSelected ? Theme.accent.opacity(0.18) : Color(.tertiarySystemGroupedBackground))
                        .foregroundStyle(isSelected ? Theme.accent : .primary)
                        .clipShape(Capsule())
                }
                .buttonStyle(.plain)
            }
        }
    }
}

// MARK: - 趋势

struct MoodTrendView: View {
    let entries: [MoodEntryModel]
    @State private var window = 7

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Picker("窗口", selection: $window) {
                    Text("最近 7 天").tag(7)
                    Text("最近 30 天").tag(30)
                }
                .pickerStyle(.segmented)

                let windowEntries = entries.filter {
                    $0.recordedAt >= Calendar.current.date(byAdding: .day, value: -window, to: Date())!
                }

                VStack(alignment: .leading, spacing: 12) {
                    Text(Strings.moodTrendTitle)
                        .font(.headline)

                    if windowEntries.count < 5 {
                        Text(Strings.moodTrendInsufficient)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    } else {
                        Chart(windowEntries.groupedByDay) { group in
                            BarMark(
                                x: .value("日期", group.date, unit: .day),
                                y: .value("平均心情", group.average)
                            )
                            .foregroundStyle(Theme.accent.gradient)
                            .cornerRadius(4)
                        }
                        .frame(height: 180)

                        Text(narrative(for: windowEntries))
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
                .cardStyle()

                Text("这些是你主动记录的分数，只是自我报告的变化，不构成任何评估或诊断。")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .padding(16)
        }
    }

    private func narrative(for windowEntries: [MoodEntryModel]) -> String {
        let average = windowEntries.map(\.score).reduce(0, +) / Double(windowEntries.count)
        var text = "过去 \(window) 天你主动记录了 \(windowEntries.count) 次心情，平均 \(String(format: "%.1f", average)) 分（满分 10）。"
        let previousStart = Calendar.current.date(byAdding: .day, value: -window * 2, to: Date())!
        let previousEnd = Calendar.current.date(byAdding: .day, value: -window, to: Date())!
        let previous = entries.filter { $0.recordedAt >= previousStart && $0.recordedAt < previousEnd }
        if previous.count >= 3 {
            let previousAverage = previous.map(\.score).reduce(0, +) / Double(previous.count)
            let diff = average - previousAverage
            let direction = diff > 0 ? "上升" : (diff < 0 ? "下降" : "持平")
            text += " 与上一个 \(window) 天相比大约\(direction) \(String(format: "%.1f", abs(diff))) 分。"
        }
        text += "这是你的自我报告变化，仅供参考。"
        return text
    }
}

extension Array where Element == MoodEntryModel {
    struct DayGroup: Identifiable {
        let date: Date
        let average: Double
        var id: Date { date }
    }

    var groupedByDay: [DayGroup] {
        Dictionary(grouping: self) {
            Calendar.current.startOfDay(for: $0.recordedAt)
        }
        .sorted { $0.key < $1.key }
        .map { key, values in
            DayGroup(date: key, average: values.map(\.score).reduce(0, +) / Double(values.count))
        }
    }
}
