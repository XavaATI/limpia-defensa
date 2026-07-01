import SwiftUI
import Photos

struct ContentView: View {
    @StateObject private var photoEngine = PhotoCleanerEngine()
    @StateObject private var dnsService = DNSSecurityService()
    @StateObject private var safariBlocker = SafariBlockerService()
    @StateObject private var storeManager = StoreKitManager()
    
    @State private var activeTab = 0
    @State private var showUpgradeSheet = false
    @State private var currentAlert: UserAlert? = nil
    
    struct UserAlert: Identifiable {
        var id: String { message }
        let title: String
        let message: String
    }
    
    var body: some View {
        TabView(selection: $activeTab) {
            // Tab 1: Dashboard
            DashboardTabView(
                photoEngine: photoEngine,
                dnsService: dnsService,
                safariBlocker: safariBlocker,
                storeManager: storeManager,
                showUpgradeSheet: $showUpgradeSheet,
                activeTab: $activeTab
            )
            .tabItem {
                Label("Status", systemImage: "gauge")
            }
            .tag(0)
            
            // Tab 2: Limpia (Photo space reclaimer)
            LimpiaTabView(
                photoEngine: photoEngine,
                storeManager: storeManager,
                showUpgradeSheet: $showUpgradeSheet,
                showAlert: { title, msg in
                    currentAlert = UserAlert(title: title, message: msg)
                }
            )
            .tabItem {
                Label("Limpia", systemImage: "photo.on.rectangle.angled")
            }
            .tag(1)
            
            // Tab 3: Defensa (Safari block & DNS)
            DefensaTabView(
                dnsService: dnsService,
                safariBlocker: safariBlocker,
                storeManager: storeManager,
                showUpgradeSheet: $showUpgradeSheet,
                showAlert: { title, msg in
                    currentAlert = UserAlert(title: title, message: msg)
                }
            )
            .tabItem {
                Label("Defensa", systemImage: "shield.fill")
            }
            .tag(2)
        }
        .preferredColorScheme(.dark)
        .accentColor(.green)
        .alert(item: $currentAlert) { alert in
            Alert(title: Text(alert.title), message: Text(alert.message), dismissButton: .default(Text("OK")))
        }
        .sheet(isPresented: $showUpgradeSheet) {
            StoreView(storeManager: storeManager) { success, msg in
                showUpgradeSheet = false
                currentAlert = UserAlert(title: success ? "PRO Unlocked" : "Store Error", message: msg)
            }
        }
    }
}

// ==============================================================================
// 1. DASHBOARD SUBVIEW
// ==============================================================================
struct DashboardTabView: View {
    @ObservedObject var photoEngine: PhotoCleanerEngine
    @ObservedObject var dnsService: DNSSecurityService
    @ObservedObject var safariBlocker: SafariBlockerService
    @ObservedObject var storeManager: StoreKitManager
    
    @Binding var showUpgradeSheet: Bool
    @Binding var activeTab: Int
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // Header card
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Limpia-Defensa")
                                .font(.title)
                                .bold()
                            Text(storeManager.isProUnlocked ? "PRO Subscription Active" : "Free Version Active")
                                .font(.subheadline)
                                .foregroundColor(.green)
                        }
                        Spacer()
                        
                        if !storeManager.isProUnlocked {
                            Button("Go PRO") {
                                showUpgradeSheet = true
                            }
                            .font(.subheadline)
                            .bold()
                            .foregroundColor(.black)
                            .padding(.vertical, 8)
                            .padding(.horizontal, 16)
                            .background(Color.green)
                            .cornerRadius(16)
                        }
                    }
                    .padding()
                    
                    // Space reclaimer preview card
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Image(systemName: "photo.on.rectangle.angled")
                                .foregroundColor(.green)
                                .font(.headline)
                            Text("Space Optimization")
                                .font(.headline)
                            Spacer()
                            Button("Open Scan") {
                                activeTab = 1
                            }
                            .foregroundColor(.green)
                        }
                        
                        Divider()
                        
                        HStack {
                            VStack(alignment: .leading) {
                                Text("\(photoEngine.duplicates.count) Duplicate Groups")
                                    .bold()
                                Text("Screenshots: \(photoEngine.screenshots.count)")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            Spacer()
                            Text(formatBytes(photoEngine.duplicates.reduce(0) { $0 + $1.totalSize }))
                                .font(.title3)
                                .bold()
                                .foregroundColor(.green)
                        }
                    }
                    .padding()
                    .background(Color.white.opacity(0.04))
                    .cornerRadius(12)
                    
                    // Defense status card
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Image(systemName: "shield.fill")
                                .foregroundColor(.green)
                                .font(.headline)
                            Text("Defense Shield")
                                .font(.headline)
                            Spacer()
                            Button("Manage") {
                                activeTab = 2
                            }
                            .foregroundColor(.green)
                        }
                        
                        Divider()
                        
                        VStack(spacing: 8) {
                            StatusRow(title: "Safari Extension", active: safariBlocker.isExtensionActive, desc: safariBlocker.statusMessage)
                            StatusRow(title: "Secure DNS (DoH)", active: dnsService.isEnabled, desc: dnsService.statusMessage)
                        }
                    }
                    .padding()
                    .background(Color.white.opacity(0.04))
                    .cornerRadius(12)
                    
                    Spacer()
                }
            }
            .navigationBarHidden(true)
        }
    }
    
    private func formatBytes(_ bytes: Int64) -> String {
        if bytes == 0 { return "0 B" }
        let sizeName = ["B", "KB", "MB", "GB", "TB"]
        let index = Int(floor(log2(Double(bytes)) / 10))
        let value = Double(bytes) / pow(1024.0, Double(index))
        return String(format: "%.2f %@", value, sizeName[index])
    }
}

struct StatusRow: View {
    let title: String
    let active: Bool
    let desc: String
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .bold()
                Text(desc)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
            Circle()
                .fill(active ? Color.green : Color.orange)
                .frame(width: 10, height: 10)
        }
    }
}

// ==============================================================================
// 2. LIMPIA (SPACE OPTIMIZER) SUBVIEW
// ==============================================================================
struct LimpiaTabView: View {
    @ObservedObject var photoEngine: PhotoCleanerEngine
    @ObservedObject var storeManager: StoreKitManager
    
    @Binding var showUpgradeSheet: Bool
    let showAlert: (String, String) -> Void
    
    var body: some View {
        NavigationView {
            VStack {
                if photoEngine.authorizationStatus == .denied || photoEngine.authorizationStatus == .restricted {
                    VStack(spacing: 16) {
                        Image(systemName: "photo.badge.exclamationmark")
                            .font(.system(size: 60))
                            .foregroundColor(.orange)
                        Text("Photo Access Required")
                            .font(.headline)
                        Text("To find duplicate photos, Limpia requires Photo Library permissions. Please enable in Settings.")
                            .multilineTextAlignment(.center)
                            .foregroundColor(.secondary)
                            .padding(.horizontal, 40)
                    }
                    .padding()
                } else if photoEngine.isScanning {
                    VStack(spacing: 16) {
                        ProgressView()
                            .scaleEffect(1.5)
                        Text("Scanning Photo Clutter...")
                            .font(.headline)
                        Text("Scanned \(photoEngine.scannedCount) photos")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                } else if photoEngine.duplicates.isEmpty && photoEngine.screenshots.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 60))
                            .foregroundColor(.green)
                        Text("Your Library is Optimized")
                            .font(.headline)
                        Button("Scan Library") {
                            requestAndScan()
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.green)
                    }
                } else {
                    List {
                        Section(header: Text("Deduplication Candidates")) {
                            ForEach(photoEngine.duplicates) { group in
                                DuplicateRow(group: group) {
                                    if !storeManager.isProUnlocked {
                                        showUpgradeSheet = true
                                    } else {
                                        // Delete the duplicates
                                        photoEngine.deleteAssets(group.duplicates) { success in
                                            if success {
                                                showAlert("Success", "Duplicate assets removed!")
                                                photoEngine.scanLibrary()
                                            } else {
                                                showAlert("Error", "Failed to remove duplicates.")
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        
                        Section(header: Text("Screenshots Clutter")) {
                            HStack {
                                Text("\(photoEngine.screenshots.count) Screenshots Found")
                                Spacer()
                                Button("Review & Prune") {
                                    if !storeManager.isProUnlocked {
                                        showUpgradeSheet = true
                                    } else {
                                        photoEngine.deleteAssets(photoEngine.screenshots) { success in
                                            if success {
                                                showAlert("Success", "Screenshots removed!")
                                                photoEngine.scanLibrary()
                                            }
                                        }
                                    }
                                }
                                .foregroundColor(.green)
                            }
                        }
                    }
                    .listStyle(InsetGroupedListStyle())
                }
            }
            .navigationTitle("Space Optimizer")
            .navigationBarItems(trailing: Button("Scan") {
                requestAndScan()
            }.foregroundColor(.green))
        }
    }
    
    private func requestAndScan() {
        photoEngine.requestAccess { granted in
            if granted {
                photoEngine.scanLibrary()
            }
        }
    }
}

struct DuplicateRow: View {
    let group: DuplicateGroup
    let pruneAction: () -> Void
    
    var body: some View {
        HStack(spacing: 16) {
            Image(systemName: "photo.on.rectangle")
                .font(.title2)
                .foregroundColor(.green)
            
            VStack(alignment: .leading, spacing: 4) {
                Text("Duplicate Group")
                    .bold()
                Text("Has \(group.duplicates.count) redundant copies")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 6) {
                Text(formatBytes(group.totalSize))
                    .bold()
                    .foregroundColor(.green)
                Button("Prune", action: pruneAction)
                    .font(.caption)
                    .padding(.vertical, 4)
                    .padding(.horizontal, 10)
                    .background(Color.green.opacity(0.12))
                    .cornerRadius(8)
            }
        }
        .padding(.vertical, 4)
    }
    
    private func formatBytes(_ bytes: Int64) -> String {
        if bytes == 0 { return "0 B" }
        let sizeName = ["B", "KB", "MB", "GB", "TB"]
        let index = Int(floor(log2(Double(bytes)) / 10))
        let value = Double(bytes) / pow(1024.0, Double(index))
        return String(format: "%.2f %@", value, sizeName[index])
    }
}

// ==============================================================================
// 3. DEFENSA (DNS & SAFARI) SUBVIEW
// ==============================================================================
struct DefensaTabView: View {
    @ObservedObject var dnsService: DNSSecurityService
    @ObservedObject var safariBlocker: SafariBlockerService
    @ObservedObject var storeManager: StoreKitManager
    
    @Binding var showUpgradeSheet: Bool
    let showAlert: (String, String) -> Void
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Safari Tracker Blocklist"), footer: Text("Limpia-Defensa Safari Extension intercepts tracking domains and scripts natively inside Safari.")) {
                    Toggle("Block Safari Trackers", isOn: Binding<Bool>(
                        get: { safariBlocker.isExtensionActive },
                        set: { _ in
                            if !storeManager.isProUnlocked {
                                showUpgradeSheet = true
                            } else {
                                safariBlocker.reloadBlockerRuleList { success, msg in
                                    showAlert(success ? "Safari Blocker" : "Extension Sync", msg)
                                }
                            }
                        }
                    ))
                    
                    HStack {
                        Text("Status")
                        Spacer()
                        Text(safariBlocker.statusMessage)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Section(header: Text("Secure Encrypted DNS (System-Wide)"), footer: Text("Runs system-wide encrypted DNS filters. Cloudflare strips malicious hosts, and AdGuard filters out ads from apps and games.")) {
                    Picker("DNS Protection Route", selection: $dnsService.activeRoute) {
                        ForEach(DNSRouteType.allCases) { route in
                            Text(route.rawValue).tag(route)
                        }
                    }
                    .onChange(of: dnsService.activeRoute) { newRoute in
                        if newRoute != .system && !storeManager.isProUnlocked {
                            dnsService.activeRoute = .system // Reset
                            showUpgradeSheet = true
                        } else {
                            dnsService.configureDNS(route: newRoute) { success, msg in
                                if !success {
                                    showAlert("DNS Configuration", msg)
                                }
                            }
                        }
                    }
                    
                    HStack {
                        Text("DNS Status")
                        Spacer()
                        Text(dnsService.statusMessage)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
            .navigationTitle("Defensa Shield")
        }
    }
}

// ==============================================================================
// 4. PRO STORE UPGRADE VIEW
// ==============================================================================
struct StoreView: View {
    @ObservedObject var storeManager: StoreKitManager
    let onComplete: (Bool, String) -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            HStack {
                Spacer()
                Button("Close") {
                    onComplete(false, "Purchase panel dismissed.")
                }
                .foregroundColor(.green)
                .font(.headline)
            }
            .padding()
            
            Image(systemName: "shield.righthalf.filled")
                .font(.system(size: 80))
                .foregroundColor(.green)
            
            Text("Limpia-Defensa PRO")
                .font(.title)
                .bold()
            
            Text("Unlock unlimited media optimization and active network-level tracker blocking.")
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
                .padding(.horizontal, 40)
            
            VStack(spacing: 12) {
                FeatureRow(title: "Unlimited Photo deduplication & cleanup")
                FeatureRow(title: "Safari Content Blocker rule reloading")
                FeatureRow(title: "System-wide Encrypted DNS server options")
                FeatureRow(title: "Fast, zero-latency network filters")
            }
            .padding(.horizontal, 30)
            .padding(.vertical, 10)
            
            Spacer()
            
            VStack(spacing: 10) {
                ForEach(PremiumProductType.allCases) { product in
                    Button(action: {
                        storeManager.purchaseProduct(product) { success, msg in
                            onComplete(success, msg)
                        }
                    }) {
                        VStack(spacing: 2) {
                            Text(product.rawValue)
                                .font(.headline)
                            Text(product.billingDescription)
                                .font(.caption)
                                .foregroundColor(.green.opacity(0.8))
                        }
                        .foregroundColor(.black)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.green)
                        .cornerRadius(12)
                    }
                    .buttonStyle(.plain)
                }
                
                Button("Restore Purchases") {
                    storeManager.restorePurchases { success, msg in
                        onComplete(success, msg)
                    }
                }
                .foregroundColor(.green)
                .font(.subheadline)
                .padding(.top, 6)
            }
            .padding(20)
        }
        .background(Color(UIColor.systemBackground))
    }
}

struct FeatureRow: View {
    let title: String
    var body: some View {
        HStack(alignment: .top) {
            Image(systemName: "checkmark.circle.fill")
                .foregroundColor(.green)
            Text(title)
                .font(.subheadline)
            Spacer()
        }
    }
}
