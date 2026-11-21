import SwiftUI

/// 温暖、低压力的视觉基调：米色背景、鼠尾草绿点缀、珊瑚色仅用于危机提示。
enum Theme {
    static let accent = Color(red: 0.36, green: 0.55, blue: 0.45)          // 鼠尾草绿
    static let background = Color(red: 0.97, green: 0.96, blue: 0.93)      // 米色
    static let bubbleUser = Color(red: 0.36, green: 0.55, blue: 0.45)
    static let bubbleAssistant = Color.white
    static let urgent = Color(red: 0.88, green: 0.42, blue: 0.33)          // 珊瑚红，仅危机场景
    static let cardCorner: CGFloat = 18
}

extension View {
    func cardStyle() -> some View {
        self
            .padding(16)
            .background(Color(.secondarySystemGroupedBackground))
            .clipShape(RoundedRectangle(cornerRadius: Theme.cardCorner))
    }
}
