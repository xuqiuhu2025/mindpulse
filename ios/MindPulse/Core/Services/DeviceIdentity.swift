import Foundation

/// 伪匿名设备标识：本地生成、Keychain 持久化，不含任何真实身份信息。
/// 删除全部数据时用户可一键重置。
enum DeviceIdentity {
    static func getOrCreate() -> String {
        let keychain = KeychainStore()
        if let existing = keychain.read("device_id"), !existing.isEmpty {
            return existing
        }
        let newID = "ios-" + UUID().uuidString
        keychain.save(newID, account: "device_id")
        return newID
    }

    static func reset() {
        KeychainStore().delete("device_id")
    }
}
