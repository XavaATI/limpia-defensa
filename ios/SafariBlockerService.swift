import Foundation
import SafariServices

class SafariBlockerService: ObservableObject {
    @Published var isExtensionActive = false
    @Published var statusMessage = "Safari blocker not running"
    
    // Replace with the bundle identifier of your Safari Content Blocker app extension target
    private let extensionIdentifier = "com.limpiadefensa.mobile.SafariBlockerExtension"
    
    init() {
        checkExtensionStatus()
    }
    
    func checkExtensionStatus() {
        // iOS 10+ lets us verify status dynamically
        SFContentBlockerManager.getStateOfContentBlocker(withIdentifier: extensionIdentifier) { state, error in
            DispatchQueue.main.async {
                if let error = error {
                    self.statusMessage = "Extension checking error: \(error.localizedDescription)"
                    self.isExtensionActive = false
                    return
                }
                
                if let state = state {
                    self.isExtensionActive = state.isEnabled
                    self.statusMessage = state.isEnabled ? "Safari content blocking active" : "Safari extension paused (Enable in Settings -> Safari)"
                } else {
                    self.isExtensionActive = false
                    self.statusMessage = "Extension not found"
                }
            }
        }
    }
    
    func reloadBlockerRuleList(completion: @escaping (Bool, String) -> Void) {
        SFContentBlockerManager.reloadContentBlocker(withIdentifier: extensionIdentifier) { error in
            DispatchQueue.main.async {
                if let error = error {
                    let errMsg = "Reload failed: \(error.localizedDescription). Please verify you have enabled 'Limpia-Defensa' in Settings -> Safari -> Extensions."
                    self.statusMessage = "Rule synchronization failed"
                    completion(false, errMsg)
                } else {
                    self.isExtensionActive = true
                    self.statusMessage = "Safari rules synchronized"
                    completion(true, "Safari Content Blocker rule lists reloaded successfully")
                }
            }
        }
    }
}
