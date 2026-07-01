import Foundation
import NetworkExtension

enum DNSRouteType: String, CaseIterable, Identifiable {
    case system = "System Default"
    case cloudflare = "Cloudflare Security (1.1.1.2)"
    case adguard = "AdGuard Ad-Block DNS"
    
    var id: String { self.rawValue }
    
    var servers: [String] {
        switch self {
        case .system: return []
        case .cloudflare: return ["1.1.1.2", "1.0.0.2", "2606:4700:4700::1112", "2606:4700:4700::1002"]
        case .adguard: return ["94.140.14.14", "94.140.15.15", "2a10:50c0::ad1:ff", "2a10:50c0::ad2:ff"]
        }
    }
    
    var dohURL: String? {
        switch self {
        case .system: return nil
        case .cloudflare: return "https://security.cloudflare-dns.com/dns-query"
        case .adguard: return "https://dns.adguard-dns.com/dns-query"
        }
    }
    
    var serverName: String? {
        switch self {
        case .system: return nil
        case .cloudflare: return "security.cloudflare-dns.com"
        case .adguard: return "dns.adguard-dns.com"
        }
    }
}

class DNSSecurityService: ObservableObject {
    @Published var isEnabled = false
    @Published var activeRoute: DNSRouteType = .system
    @Published var statusMessage = "DNS settings inactive"
    
    private let manager = NEDNSSettingsManager.shared()
    
    init() {
        refreshStatus()
    }
    
    func refreshStatus() {
        manager.loadFromPreferences { error in
            DispatchQueue.main.async {
                if let error = error {
                    self.statusMessage = "Failed to load DNS profile: \(error.localizedDescription)"
                    return
                }
                
                if let settings = self.manager.dnsSettings {
                    self.isEnabled = self.manager.isEnabled
                    // Deduce which route is active
                    if let dnsOverHTTPS = settings as? NEDNSOverHTTPSSettings {
                        if dnsOverHTTPS.serverURL?.absoluteString.contains("adguard") == true {
                            self.activeRoute = .adguard
                        } else if dnsOverHTTPS.serverURL?.absoluteString.contains("cloudflare") == true {
                            self.activeRoute = .cloudflare
                        }
                    }
                    self.statusMessage = self.isEnabled ? "Active: Encrypted \(self.activeRoute.rawValue)" : "Encrypted DNS profile paused"
                } else {
                    self.isEnabled = false
                    self.activeRoute = .system
                    self.statusMessage = "Using ISP default unencrypted DNS"
                }
            }
        }
    }
    
    func configureDNS(route: DNSRouteType, completion: @escaping (Bool, String) -> Void) {
        manager.loadFromPreferences { error in
            if let error = error {
                DispatchQueue.main.async {
                    completion(false, "Load Error: \(error.localizedDescription)")
                }
                return
            }
            
            if route == .system {
                // Remove custom configuration
                self.manager.dnsSettings = nil
                self.manager.isEnabled = false
            } else {
                // Setup DNS-over-HTTPS (DoH) settings
                let settings = NEDNSOverHTTPSSettings(servers: route.servers)
                if let dohURLStr = route.dohURL, let url = URL(string: dohURLStr) {
                    settings.serverURL = url
                }
                settings.serverName = route.serverName
                
                self.manager.dnsSettings = settings
                self.manager.localizedDescription = "Limpia-Defensa Secure DNS Protection"
                self.manager.isEnabled = true
            }
            
            self.manager.saveToPreferences { saveError in
                DispatchQueue.main.async {
                    if let saveError = saveError {
                        // Commonly fails on Simulator due to lack of NetworkExtension entitlements
                        let failMsg = "Save failed. In actual App Store builds, this prompts the user for VPN/DNS configuration installation: \(saveError.localizedDescription)"
                        self.statusMessage = "Profile setup rejected"
                        completion(false, failMsg)
                    } else {
                        self.activeRoute = route
                        self.isEnabled = (route != .system)
                        self.statusMessage = self.isEnabled ? "Active: Encrypted \(route.rawValue)" : "Using system default DNS"
                        completion(true, "DNS Settings profile updated successfully")
                    }
                }
            }
        }
    }
}
