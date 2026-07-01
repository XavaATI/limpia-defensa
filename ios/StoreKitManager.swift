import Foundation
import StoreKit

enum PremiumProductType: String, CaseIterable, Identifiable {
    case weeklyPro = "Weekly Pro Plan ($1.99)"
    case monthlyPro = "Monthly Pro Plan ($4.99)"
    case lifetimePro = "Lifetime Pro Purchase ($19.99)"
    
    var id: String { self.rawValue }
    
    var price: String {
        switch self {
        case .weeklyPro: return "$1.99"
        case .monthlyPro: return "$4.99"
        case .lifetimePro: return "$19.99"
        }
    }
    
    var billingDescription: String {
        switch self {
        case .weeklyPro: return "billed weekly, cancel anytime"
        case .monthlyPro: return "billed monthly, popular choice"
        case .lifetimePro: return "one-time payment, lifetime security"
        }
    }
}

class StoreKitManager: ObservableObject {
    @Published var isProUnlocked = false
    @Published var activeProduct: PremiumProductType? = nil
    @Published var purchaseStatus = "Free Version Active"
    
    private let userDefaultsKey = "com.limpiadefensa.mobile.isProUnlocked"
    private let activeProductKey = "com.limpiadefensa.mobile.activeProduct"
    
    init() {
        // Load local purchase states
        self.isProUnlocked = UserDefaults.standard.bool(forKey: userDefaultsKey)
        if let savedProduct = UserDefaults.standard.string(forKey: activeProductKey) {
            self.activeProduct = PremiumProductType(rawValue: savedProduct)
        }
        
        self.purchaseStatus = self.isProUnlocked ? "Limpia-Defensa PRO Active" : "Free Version Active (Scan only)"
    }
    
    @MainActor
    func purchaseProduct(_ productType: PremiumProductType, completion: @escaping (Bool, String) -> Void) {
        // Simulate purchase transaction (for Sandbox testing out of the box)
        self.purchaseStatus = "Contacting Apple Store..."
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            self.isProUnlocked = true
            self.activeProduct = productType
            
            UserDefaults.standard.set(true, forKey: self.userDefaultsKey)
            UserDefaults.standard.set(productType.rawValue, forKey: self.activeProductKey)
            
            self.purchaseStatus = "Limpia-Defensa PRO Active"
            
            completion(true, "Transaction Succeeded: Thank you for upgrading to \(productType.rawValue)!")
        }
    }
    
    @MainActor
    func restorePurchases(completion: @escaping (Bool, String) -> Void) {
        self.purchaseStatus = "Restoring credentials..."
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            // Check local configuration
            let wasUnlocked = UserDefaults.standard.bool(forKey: self.userDefaultsKey)
            self.isProUnlocked = wasUnlocked
            
            if wasUnlocked {
                self.purchaseStatus = "Limpia-Defensa PRO Restored"
                completion(true, "Purchases Restored: Pro privileges unlocked!")
            } else {
                self.purchaseStatus = "No active purchases found"
                completion(false, "Restore complete: No active premium subscription found.")
            }
        }
    }
    
    @MainActor
    func deactivatePro() {
        self.isProUnlocked = false
        self.activeProduct = nil
        UserDefaults.standard.set(false, forKey: self.userDefaultsKey)
        UserDefaults.standard.removeObject(forKey: self.activeProductKey)
        self.purchaseStatus = "Free Version Active"
    }
}
