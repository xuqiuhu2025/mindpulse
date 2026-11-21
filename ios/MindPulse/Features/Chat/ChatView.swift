import SwiftUI

struct ChatView: View {
    @EnvironmentObject private var environment: AppEnvironment
    @EnvironmentObject private var chat: ChatService
    @State private var draft = ""

    var body: some View {
        VStack(spacing: 0) {
            messageList
            composer
            disclaimerFooter
        }
        .background(Theme.background)
        .navigationTitle("MindPulse")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Button(role: .destructive) {
                        chat.clearCurrentConversation()
                    } label: {
                        Label("清空当前对话", systemImage: "eraser")
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
        }
        .sheet(isPresented: Binding(
            get: { chat.activeCrisis != nil },
            set: { if !$0 { chat.activeCrisis = nil } }
        )) {
            if let crisis = chat.activeCrisis {
                CrisisResourcesSheet(crisis: crisis)
            }
        }
    }

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    Text(chat.greeting())
                        .font(.title3)
                        .fontWeight(.semibold)
                        .foregroundStyle(.primary)
                        .padding(.top, 8)

                    if chat.messages.isEmpty {
                        starterChips
                    }

                    ForEach(chat.messages) { message in
                        ChatBubble(message: message)
                            .id(message.id)
                    }

                    if chat.isThinking {
                        HStack(spacing: 8) {
                            ProgressView()
                            Text("正在想…")
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                        .padding(.horizontal, 16)
                    }

                    if let notice = chat.offlineNotice {
                        Label(notice, systemImage: "wifi.slash")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                            .cardStyle()
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 8)
            }
            .onChange(of: chat.messages.count) { _, _ in
                if let last = chat.messages.last {
                    withAnimation(.easeOut(duration: 0.2)) {
                        proxy.scrollTo(last.id, anchor: .bottom)
                    }
                }
            }
        }
    }

    private var starterChips: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("可以试着说：")
                .font(.footnote)
                .foregroundStyle(.secondary)
            ForEach(ChatService.starterPrompts, id: \.self) { prompt in
                Button {
                    draft = prompt
                    Task { await send() }
                } label: {
                    Text(prompt)
                        .font(.subheadline)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .background(Color.white.opacity(0.9))
                        .clipShape(Capsule())
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.top, 4)
    }

    private var composer: some View {
        HStack(spacing: 10) {
            TextField("说点什么…", text: $draft, axis: .vertical)
                .textFieldStyle(.plain)
                .lineLimit(1...4)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(Color.white)
                .clipShape(Capsule())

            Button {
                Task { await send() }
            } label: {
                Image(systemName: "paperplane.fill")
                    .padding(10)
            }
            .disabled(draft.trimmingCharacters(in: .whitespaces).isEmpty || chat.isThinking)
            .background(Theme.accent)
            .foregroundStyle(.white)
            .clipShape(Circle())
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
    }

    private var disclaimerFooter: some View {
        Text(Strings.disclaimer)
            .font(.caption2)
            .foregroundStyle(.secondary)
            .multilineTextAlignment(.center)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 6)
            .background(Theme.background.opacity(0.001))
    }

    private func send() async {
        let text = draft
        draft = ""
        await chat.send(text)
    }
}

struct ChatBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack(alignment: .bottom) {
            if message.role == .user { Spacer(minLength: 48) }
            Text(message.text)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(message.role == .user ? Theme.bubbleUser : Theme.bubbleAssistant)
                .foregroundStyle(message.role == .user ? .white : .primary)
                .clipShape(RoundedRectangle(cornerRadius: 18))
            if message.role == .assistant { Spacer(minLength: 48) }
        }
    }
}
