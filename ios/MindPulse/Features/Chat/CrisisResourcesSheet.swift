import SwiftUI

/// 危机资源页：urgent 场景展示。
/// 国家列表只用于定位"经过验证的本地资源"；MindPulse 不硬编码任何单一号码作为唯一指引，
/// 国际目录始终可用，未知地区会先询问用户。
struct CrisisResourcesSheet: View {
    let crisis: CrisisInfoDTO

    @State private var resources: CrisisInfoDTO?
    @State private var selectedCountry: String?

    static let countryOptions: [(code: String, name: String)] = [
        ("CN", "中国"), ("US", "美国"), ("GB", "英国"), ("CA", "加拿大"),
        ("AU", "澳大利亚"), ("NZ", "新西兰"), ("JP", "日本"), ("KR", "韩国"),
        ("DE", "德国"), ("FR", "法国"), ("ES", "西班牙"), ("BR", "巴西"),
        ("IN", "印度"), ("SG", "新加坡"),
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    urgentBanner
                    body
                }
                .padding(16)
            }
            .navigationTitle("危机支持")
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private var urgentBanner: some View {
        Label(Strings.crisisBanner, systemImage: "exclamationmark.triangle.fill")
            .font(.subheadline)
            .fontWeight(.semibold)
            .foregroundStyle(.white)
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.urgent)
            .clipShape(RoundedRectangle(cornerRadius: Theme.cardCorner))
    }

    @ViewBuilder
    private var body: some View {
        let info = resources ?? crisis

        if info.needCountry {
            VStack(alignment: .leading, spacing: 10) {
                Text(info.note ?? "请告诉我你所在的国家或地区，我来帮你查找当地支持。")
                    .font(.subheadline)
                ForEach(Self.countryOptions, id: \.code) { option in
                    Button {
                        selectedCountry = option.code
                        Task { await load(country: option.code) }
                    } label: {
                        Text(option.name)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(12)
                            .background(Color(.secondarySystemGroupedBackground))
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    .buttonStyle(.plain)
                }
            }
        } else {
            VStack(alignment: .leading, spacing: 12) {
                if let emergency = info.emergencyNumber {
                    ResourceRow(
                        title: "当地急救电话",
                        detail: emergency,
                        phone: emergency,
                        highlight: true
                    )
                }
                ForEach(info.resources) { resource in
                    ResourceRow(
                        title: resource.name,
                        detail: [resource.phone, resource.hours].compactMap { $0 }.joined(separator: " · "),
                        phone: resource.phone
                    )
                }
                Text(info.note ?? "")
                    .font(.footnote)
                    .foregroundStyle(.secondary)

                Divider()
                VStack(alignment: .leading, spacing: 6) {
                    Text("国际求助目录")
                        .font(.footnote)
                        .fontWeight(.semibold)
                    ForEach(info.directories, id: \.self) { dir in
                        Link(dir, destination: URL(string: dir)!)
                            .font(.footnote)
                    }
                }
            }
        }
    }

    private func load(country: String) async {
        resources = crisis
        // 重新按所选国家拉取资源（走公开接口，无需设备标识）
        let client = APIClient(serverURL: serverURL, deviceID: "sheet-local")
        if let info = try? await client.fetchCrisisResources(country: country) {
            resources = info
        }
    }

    private var serverURL: URL {
        URL(string: UserDefaults.standard.string(forKey: "mp_server_url") ?? "http://127.0.0.1:8000")
            ?? URL(string: "http://127.0.0.1:8000")!
    }
}

struct ResourceRow: View {
    let title: String
    let detail: String
    let phone: String?
    var highlight = false

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.subheadline)
                    .fontWeight(highlight ? .semibold : .regular)
                Text(detail)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            if let phone, let url = URL(string: "tel://\(phone.replacingOccurrences(of: " ", with: ""))") {
                Link(destination: url) {
                    Image(systemName: "phone.fill")
                        .padding(10)
                }
                .background(highlight ? Theme.urgent : Theme.accent)
                .foregroundStyle(.white)
                .clipShape(Circle())
            }
        }
        .padding(12)
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}
