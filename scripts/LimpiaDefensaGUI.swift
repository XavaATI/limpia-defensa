import SwiftUI
import AppKit
import Security
import Darwin

// ==============================================================================
// 📝 PERSISTENT LOGGER ENGINE
// ==============================================================================
class LDPersistentLogger {
    static let shared = LDPersistentLogger()
    private let logFileURL: URL
    private let lock = NSLock()
    private let dateFormatter: DateFormatter
    
    private init() {
        let libraryDirectory = FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask).first!
        let logsDirectory = libraryDirectory.appendingPathComponent("Logs")
        
        // Ensure Library/Logs exists
        try? FileManager.default.createDirectory(at: logsDirectory, withIntermediateDirectories: true)
        logFileURL = logsDirectory.appendingPathComponent("LimpiaDefensa.log")
        
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        self.dateFormatter = formatter
        
        log(level: "INFO", message: "=== Limpia-Defensa System Initialised ===")
    }
    
    private func logUnlocked(level: String, message: String) {
        let timestamp = dateFormatter.string(from: Date())
        let logLine = "[\(timestamp)] [\(level)] \(message)\n"
        
        if let data = logLine.data(using: .utf8) {
            if FileManager.default.fileExists(atPath: logFileURL.path) {
                if let fileHandle = try? FileHandle(forWritingTo: logFileURL) {
                    _ = try? fileHandle.seekToEnd()
                    try? fileHandle.write(contentsOf: data)
                    try? fileHandle.close()
                }
            } else {
                try? data.write(to: logFileURL)
            }
        }
        print(logLine, terminator: "")
    }
    
    func log(level: String, message: String) {
        lock.lock()
        defer { lock.unlock() }
        logUnlocked(level: level, message: message)
    }
    
    func readLogs() -> String {
        lock.lock()
        defer { lock.unlock() }
        return (try? String(contentsOf: logFileURL, encoding: .utf8)) ?? "No log file found."
    }
    
    func clearLogs() {
        lock.lock()
        defer { lock.unlock() }
        try? "".write(to: logFileURL, atomically: true, encoding: .utf8)
        logUnlocked(level: "INFO", message: "Log buffer cleared by user configuration")
    }
}

// ==============================================================================
// 🛡️ NATIVE C API BINDINGS (Darwin / libproc)
// ==============================================================================
@_silgen_name("proc_listallpids")
func proc_listallpids(_ buffer: UnsafeMutableRawPointer?, _ buffersize: Int32) -> Int32

@_silgen_name("proc_pidpath")
func proc_pidpath(_ pid: Int32, _ buffer: UnsafeMutableRawPointer?, _ buffersize: UInt32) -> Int32

@_silgen_name("proc_pidinfo")
func proc_pidinfo(_ pid: Int32, _ flavor: Int32, _ arg: UInt64, _ buffer: UnsafeMutableRawPointer?, _ buffersize: Int32) -> Int32

@_silgen_name("proc_pidfdinfo")
func proc_pidfdinfo(_ pid: Int32, _ fd: Int32, _ flavor: Int32, _ buffer: UnsafeMutableRawPointer?, _ buffersize: Int32) -> Int32

func formatBytes(_ bytes: Int64) -> String {
    if bytes == 0 { return "0 B" }
    let sizeName = ["B", "KB", "MB", "GB", "TB"]
    let index = Int(floor(log2(Double(bytes)) / 10))
    let value = Double(bytes) / pow(1024.0, Double(index))
    return String(format: "%.2f %@", value, sizeName[index])
}

// ==============================================================================
// ✊ SWIFT DECODABLE STRUCTURES (JSON matching limpia_defensa.py outputs)
// ==============================================================================
struct CacheItem: Codable, Identifiable {
    var id: String { path }
    let name: String
    let path: String
    let size: Int64
    let size_str: String
    let files_count: Int
}

struct LogItem: Codable, Identifiable {
    var id: String { path }
    let name: String
    let path: String
    let size: Int64
    let size_str: String
    let files_count: Int
}

struct InstallerItem: Codable, Identifiable {
    var id: String { path }
    let name: String
    let path: String
    let size: Int64
    let size_str: String
}

struct DuplicateGroup: Codable, Identifiable {
    var id: String { hash }
    let size: Int64
    let size_str: String
    let hash: String
    let paths: [String]
}

struct OrphanItem: Codable, Identifiable {
    var id: String { path }
    let name: String
    let path: String
    let size: Int64
    let size_str: String
}

struct MediaItem: Codable, Identifiable {
    var id: String { path }
    let name: String
    let path: String
    let size: Int64
    let size_str: String
}

struct ScanCategories: Codable {
    let caches: [CacheItem]
    let developer_caches: [CacheItem]?
    let ai_model_caches: [CacheItem]?
    let trash: [CacheItem]?
    let browser_caches: [CacheItem]?
    let logs: [LogItem]
    let installers: [InstallerItem]
    let duplicates: [DuplicateGroup]
    let orphans: [OrphanItem]
    let vms: [MediaItem]?
    let videos: [MediaItem]?
    let photos: [MediaItem]?
    let archives: [MediaItem]?
}

struct ScanSummary: Codable {
    let reclaimable_size: Int64
    let reclaimable_str: String
}

struct ScanResults: Codable {
    let timestamp: String
    let gdrive_connected: Bool
    let categories: ScanCategories
    let summary: ScanSummary
}

struct BackupSession: Codable, Identifiable {
    var id: String { session }
    let session: String
    let file_count: Int
    let size: Int64
    let size_str: String
    let categories: [String]
    let encrypted: Bool?
}

struct BackupListResponse: Codable {
    let connected: Bool
    let backups: [BackupSession]
}

// ==============================================================================
// 🦅 QUETZAL CORE: HIGH-PERFORMANCE IN-MEMORY ACTIVE THREAT ENGINE
// ==============================================================================
struct ThreatProcess: Identifiable, Codable {
    var id: String { "\(pid)_\(path)" }
    let pid: Int32
    let path: String
    let name: String
    let isSigned: Bool
    let isDeletedOnLaunch: Bool
    let hasSockets: Bool
    let isCritical: Bool
    let reason: String
}

class QuetzalCore {
    static func runActiveScan() -> [ThreatProcess] {
        LDPersistentLogger.shared.log(level: "INFO", message: "Starting Quetzal Core memory process sweep...")
        let count = proc_listallpids(nil, 0)
        guard count > 0 else { return [] }
        var pids = [pid_t](repeating: 0, count: Int(count))
        let bytesWritten = pids.withUnsafeMutableBytes { bufPtr in
            proc_listallpids(bufPtr.baseAddress, Int32(count * Int32(MemoryLayout<pid_t>.size)))
        }
        guard bytesWritten > 0 else { return [] }
        let actualCount = Int(bytesWritten) / MemoryLayout<pid_t>.size
        let pidsList = Array(pids.prefix(actualCount))
        
        var results: [ThreatProcess] = []
        let currentPID = getpid()
        
        for pid in pidsList {
            if pid <= 0 || pid == currentPID { continue }
            
            // Resolve executable path safely
            var pathBuffer = [UInt8](repeating: 0, count: Int(MAXPATHLEN) + 1)
            let length = pathBuffer.withUnsafeMutableBytes { bufPtr in
                proc_pidpath(pid, bufPtr.baseAddress, UInt32(MAXPATHLEN))
            }
            let path = length > 0 ? String(cString: pathBuffer) : ""
            
            if path.isEmpty { continue }
            
            // Skip SIP protected and system directories for raw performance
            if path.hasPrefix("/System/") || 
               path.hasPrefix("/usr/bin/") || 
               path.hasPrefix("/usr/sbin/") || 
               path.hasPrefix("/usr/libexec/") || 
               path.hasPrefix("/bin/") || 
               path.hasPrefix("/sbin/") || 
               path.hasPrefix("/Library/Developer/") {
                continue
            }
            
            // Avoid expensive URL allocation to get last path component
            let name: String
            if let lastSlash = path.lastIndex(of: "/") {
                name = String(path[path.index(after: lastSlash)...])
            } else {
                name = path
            }
            
            // 1. Check if executable deleted on launch (evasion)
            let fileExists = FileManager.default.fileExists(atPath: path)
            let isDeletedOnLaunch = !fileExists
            
            // 2. Validate code signature
            var isSigned = false
            if fileExists {
                let url = URL(fileURLWithPath: path)
                var staticCode: SecStaticCode?
                let status = SecStaticCodeCreateWithPath(url as CFURL, [], &staticCode)
                if status == errSecSuccess, let code = staticCode {
                    let validityStatus = SecStaticCodeCheckValidity(code, SecCSFlags(rawValue: 0), nil)
                    isSigned = (validityStatus == errSecSuccess)
                }
            }
            
            // 3. Inspect socket connections via proc_pidinfo
            var hasSockets = false
            let fdBufferSize = proc_pidinfo(pid, 1, 0, nil, 0) // PROC_PIDLISTFDS is 1
            if fdBufferSize > 0 {
                let rawFds = UnsafeMutableRawPointer.allocate(byteCount: Int(fdBufferSize), alignment: 8)
                defer { rawFds.deallocate() }
                
                let bytesFilled = proc_pidinfo(pid, 1, 0, rawFds, fdBufferSize)
                let actualFdCount = Int(bytesFilled) / 8
                
                if actualFdCount > 0 {
                    let rawBuffer = UnsafeRawBufferPointer(start: rawFds, count: Int(bytesFilled))
                    for i in 0..<actualFdCount {
                        let fd = rawBuffer.load(fromByteOffset: i * 8, as: Int32.self)
                        let type = rawBuffer.load(fromByteOffset: i * 8 + 4, as: Int32.self)
                        
                        if type == 2 { // PROX_FDTYPE_SOCKET is 2
                            let socketInfoSize: Int32 = 792 // sizeof(struct socket_fdinfo)
                            var socketBuffer = [UInt8](repeating: 0, count: Int(socketInfoSize))
                            let bytesFetched = proc_pidfdinfo(pid, fd, 3, &socketBuffer, socketInfoSize) // PROC_PIDFDSOCKETINFO is 3
                            
                            if bytesFetched == socketInfoSize {
                                socketBuffer.withUnsafeBytes { rawBufPtr in
                                    // Read family at byte offset 184 (within struct socket_fdinfo)
                                    let family = rawBufPtr.load(fromByteOffset: 184, as: Int32.self)
                                    if family == 2 || family == 30 { // AF_INET (2) or AF_INET6 (30)
                                        hasSockets = true
                                    }
                                }
                            }
                        }
                        if hasSockets { break }
                    }
                }
            }
            
            // Risk assessment
            let isHighRiskPath = path.hasPrefix("/Users/") || path.hasPrefix("/tmp/") || path.hasPrefix("/private/var/") || path.hasPrefix("/var/tmp/")
            var isCritical = false
            var reason = ""
            
            if isDeletedOnLaunch {
                isCritical = true
                reason = "Binary deleted from disk after execution (Evasion)"
            } else if !isSigned && isHighRiskPath {
                isCritical = true
                reason = "Unsigned binary executing from user path"
            } else if !isSigned {
                reason = "Unsigned process running"
            }
            
            if hasSockets && !isSigned {
                isCritical = true
                reason += (reason.isEmpty ? "" : " + ") + "Active remote socket connection"
            }
            
            if isCritical || !isSigned || isDeletedOnLaunch {
                results.append(ThreatProcess(
                    pid: pid,
                    path: path,
                    name: name,
                    isSigned: isSigned,
                    isDeletedOnLaunch: isDeletedOnLaunch,
                    hasSockets: hasSockets,
                    isCritical: isCritical,
                    reason: reason
                ))
            }
        }
        
        LDPersistentLogger.shared.log(level: "INFO", message: "Quetzal Core sweep completed. Registered \(results.count) items.")
        return results
    }
}

// ==============================================================================
// 📱 NATIVE SWIFTUI GUI LAYOUT
// ==============================================================================
enum NavigationTab: String, CaseIterable, Identifiable {
    case dashboard = "Dashboard"
    case cleanup = "System Cleanup"
    case quetzalCore = "Quetzal Core AV"
    case backups = "Backup & Restore"
    case about = "About & Help"
    
    var id: String { self.rawValue }
    var iconName: String {
        switch self {
        case .dashboard: return "gauge"
        case .cleanup: return "trash"
        case .quetzalCore: return "shield.fill"
        case .backups: return "arrow.clockwise.icloud"
        case .about: return "info.circle"
        }
    }
}

struct VisualEffectView: NSViewRepresentable {
    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.blendingMode = .behindWindow
        view.state = .active
        view.material = .hudWindow
        return view
    }
    func updateNSView(_ nsView: NSVisualEffectView, context: Context) {}
}

class HostingWindowView: NSView {
    var callback: ((NSWindow) -> Void)?
    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        if let window = self.window {
            callback?(window)
        }
    }
}

struct WindowAccessor: NSViewRepresentable {
    let callback: (NSWindow) -> Void
    func makeNSView(context: Context) -> HostingWindowView {
        let view = HostingWindowView()
        view.callback = callback
        return view
    }
    func updateNSView(_ nsView: HostingWindowView, context: Context) {}
}

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            self.positionOnPrimaryScreen()
        }
    }
    
    func positionOnPrimaryScreen() {
        guard let screen = NSScreen.screens.first else { return }
        let vf = screen.visibleFrame
        let width: CGFloat = min(960, vf.width - 60)
        let height: CGFloat = min(640, vf.height - 60)
        let x = vf.origin.x + (vf.width - width) / 2
        let y = vf.origin.y + (vf.height - height) / 2
        let rect = NSRect(x: x, y: y, width: width, height: height)
        
        for window in NSApp.windows {
            window.setFrame(rect, display: true, animate: false)
            window.makeKeyAndOrderFront(nil)
            window.orderFrontRegardless()
        }
        NSApp.activate(ignoringOtherApps: true)
    }
    
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }
}

@main
struct LimpiaDefensaGUIApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    init() {
        NSApplication.shared.setActivationPolicy(.regular)
        LDPersistentLogger.shared.log(level: "INFO", message: "Core Application launching...")
    }
    
    var body: some Scene {
        WindowGroup {
            MainContainerView()
                .preferredColorScheme(.dark)
                .onAppear {
                    NSApp.setActivationPolicy(.regular)
                    NSApp.activate(ignoringOtherApps: true)
                    appDelegate.positionOnPrimaryScreen()
                }
        }
        .windowStyle(.titleBar)
        .defaultSize(width: 960, height: 640)
    }
}

struct MainContainerView: View {
    @State private var activeTab: NavigationTab = .dashboard
    
    // Core Engine States
    @State private var scanResults: ScanResults? = nil
    @State private var backups: [BackupSession] = []
    @State private var activeThreats: [ThreatProcess] = []
    
    // Loading Indicators
    @State private var isScanning = false
    @State private var isCleaning = false
    @State private var isThreatScanning = false
    @State private var isRestoring = false
    @State private var gdriveConnected = false
    
    // Selection and logs
    @State private var selectedCategories: Set<String> = ["caches", "developer_caches", "logs", "trash"]
    @State private var consoleLog: String = ""
    @State private var errorMessage: String? = nil
    @State private var useSudo = false
    
    // V1.2 Backup Target and Security States
    @State private var backupType: String = "cloud" // "cloud", "local", "network"
    @State private var customBackupPath: String = ""
    @State private var encryptBackups: Bool = false
    @State private var encryptionPassphrase: String = ""
    
    // V1.2 Advanced Mode and Rollback States
    @State private var advancedMode: Bool = false
    @State private var isRollingBack = false
    
    // Delta Tracking, Separate Cleanup and AV Quarantine States
    @State private var sizeBeforeClean: Int64 = 0
    @State private var sizeAfterClean: Int64 = 0
    @State private var cleanHasRun = false
    @State private var runningIndividualTask: String? = nil
    
    // Cloud/Disk Migration States
    @State private var isMigrating = false
    @State private var isMigrationPaused = false
    @State private var migrationLog = ""
    
    var body: some View {
        NavigationView {
            // Sidebar Panel
            List(NavigationTab.allCases) { tab in
                NavigationButton(tab: tab, activeTab: $activeTab)
            }
            .listStyle(SidebarListStyle())
            .frame(minWidth: 180, idealWidth: 200)
            .background(VisualEffectView())
            
            // Detail Panel
            DetailRouterView(
                tab: activeTab,
                scanResults: $scanResults,
                backups: $backups,
                activeThreats: $activeThreats,
                isScanning: $isScanning,
                isCleaning: $isCleaning,
                runningIndividualTask: $runningIndividualTask,
                isThreatScanning: $isThreatScanning,
                isRestoring: $isRestoring,
                gdriveConnected: $gdriveConnected,
                selectedCategories: $selectedCategories,
                consoleLog: $consoleLog,
                errorMessage: $errorMessage,
                useSudo: $useSudo,
                backupType: $backupType,
                customBackupPath: $customBackupPath,
                encryptBackups: $encryptBackups,
                encryptionPassphrase: $encryptionPassphrase,
                advancedMode: $advancedMode,
                isRollingBack: $isRollingBack,
                cleanHasRun: $cleanHasRun,
                sizeBeforeClean: $sizeBeforeClean,
                sizeAfterClean: $sizeAfterClean,
                isMigrating: $isMigrating,
                isMigrationPaused: $isMigrationPaused,
                migrationLog: $migrationLog,
                triggerScan: triggerScan,
                triggerClean: triggerClean,
                triggerCleanSingle: triggerCleanSingle,
                triggerQuarantine: triggerQuarantine,
                triggerThreatScan: triggerThreatScan,
                triggerBackupsList: triggerBackupsList,
                triggerRestore: triggerRestore,
                triggerRollback: triggerRollback,
                triggerMigration: triggerMigration,
                toggleMigrationPause: toggleMigrationPause,
                checkMigrationPauseState: checkMigrationPauseState,
                startOver: startOver
            )
            .frame(minWidth: 650, minHeight: 520)
        }
        .frame(minWidth: 850, minHeight: 550)
        .background(WindowAccessor { window in
            guard let screen = NSScreen.screens.first else { return }
            let vf = screen.visibleFrame
            let w: CGFloat = min(960, vf.width - 40)
            let h: CGFloat = min(640, vf.height - 40)
            let x = vf.origin.x + (vf.width - w) / 2
            let y = vf.origin.y + (vf.height - h) / 2
            window.setFrame(NSRect(x: x, y: y, width: w, height: h), display: true, animate: false)
            window.makeKeyAndOrderFront(nil)
            window.orderFrontRegardless()
            NSApp.activate(ignoringOtherApps: true)
        })
        .alert(item: Binding<AlertError?>(
            get: { errorMessage.map { AlertError(message: $0) } },
            set: { errorMessage = $0?.message }
        )) { error in
            Alert(title: Text("Engine Operational Warning"),
                  message: Text(error.message),
                  dismissButton: .default(Text("Acknowledge")))
        }
        .onAppear {
            LDPersistentLogger.shared.log(level: "INFO", message: "Main container loaded, starting audits.")
            triggerScan()
            triggerBackupsList()
            triggerThreatScan()
            checkMigrationPauseState()
        }
        .onChange(of: advancedMode) { oldVal, newVal in
            if !newVal {
                LDPersistentLogger.shared.log(level: "INFO", message: "Advanced mode deactivated: resetting high-risk categories.")
                selectedCategories.remove("orphans")
                selectedCategories.remove("duplicates")
                useSudo = false
            }
        }
    }
    
    struct AlertError: Identifiable {
        var id: String { message }
        let message: String
    }
    
    // ==============================================================================
    // ⚙️ ASYNCHRONOUS BACKEND PROCESS COMMUNICATORS
    // ==============================================================================
    private func getPythonPath() -> String {
        for path in ["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"] {
            if FileManager.default.fileExists(atPath: path) {
                return path
            }
        }
        return "python3"
    }
    
    private func getWorkspacePath() -> String {
        return "/Users/xavasena/collectivo/limpiada"
    }
    
    private func runScript(scriptName: String, args: [String], elevate: Bool = false) async -> (Int32, String) {
        let pythonPath = getPythonPath()
        let scriptPath = getWorkspacePath() + "/scripts/" + scriptName
        
        LDPersistentLogger.shared.log(level: "INFO", message: "Launching script \(scriptName) (elevate: \(elevate)): \(args.joined(separator: " "))")
        
        let task = Process()
        
        if elevate {
            task.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
            
            var osascriptArgs: [String] = [
                "-e", "on run argv",
                "-e", "    set cmd to \"cd \" & quoted form of \"" + getWorkspacePath() + "\" & \" && HOME=/Users/xavasena \"",
                "-e", "    repeat with arg in argv",
                "-e", "        set cmd to cmd & \" \" & quoted form of arg",
                "-e", "    end repeat",
                "-e", "    do shell script cmd with administrator privileges",
                "-e", "end run"
            ]
            
            osascriptArgs.append(pythonPath)
            osascriptArgs.append(scriptPath)
            osascriptArgs.append(contentsOf: args)
            
            task.arguments = osascriptArgs
            
            let loggedCmd = "HOME=/Users/xavasena " + ([pythonPath, scriptPath] + args).map { "'\($0.replacingOccurrences(of: "'", with: "'\\''"))'" }.joined(separator: " ")
            LDPersistentLogger.shared.log(level: "INFO", message: "Elevated command via osascript (argv wrapper): \(loggedCmd)")
        } else {
            task.executableURL = URL(fileURLWithPath: pythonPath)
            task.arguments = [scriptPath] + args
        }
        
        task.currentDirectoryURL = URL(fileURLWithPath: getWorkspacePath())
        
        let outPipe = Pipe()
        let errPipe = Pipe()
        task.standardOutput = outPipe
        task.standardError = errPipe
        
        let outTask = Task { () -> Data in
            let data = (try? outPipe.fileHandleForReading.readToEnd()) ?? Data()
            try? outPipe.fileHandleForReading.close()
            return data
        }
        
        let errTask = Task { () -> Data in
            let data = (try? errPipe.fileHandleForReading.readToEnd()) ?? Data()
            try? errPipe.fileHandleForReading.close()
            return data
        }
        
        do {
            try task.run()
            task.waitUntilExit()
            
            let outData = await outTask.value
            let errData = await errTask.value
            
            let output = String(data: outData, encoding: .utf8) ?? ""
            let error = String(data: errData, encoding: .utf8) ?? ""
            
            LDPersistentLogger.shared.log(level: "INFO", message: "Script \(scriptName) finished. Status: \(task.terminationStatus)")
            if task.terminationStatus == 0 {
                return (0, output)
            } else {
                return (task.terminationStatus, error.isEmpty ? output : error)
            }
        } catch {
            LDPersistentLogger.shared.log(level: "ERROR", message: "Script failed to spawn: \(error.localizedDescription)")
            return (-1, "Process Execution Error: \(error.localizedDescription)")
        }
    }
    
    private func getBackupArgs() -> [String] {
        var args = ["--backup-type", backupType]
        let path = customBackupPath.trimmingCharacters(in: .whitespacesAndNewlines)
        if !path.isEmpty {
            args.append(contentsOf: ["--backup-path", path])
        }
        return args
    }
    
    private func getEncryptionArgs(isClean: Bool = false) -> [String] {
        var args: [String] = []
        if encryptBackups {
            if isClean {
                args.append("--encrypt")
            }
            let pass = encryptionPassphrase.trimmingCharacters(in: .whitespacesAndNewlines)
            if !pass.isEmpty {
                args.append(contentsOf: ["--passphrase", pass])
            }
        }
        return args
    }
    
    private func triggerScan() {
        guard !isScanning else { return }
        isScanning = true
        LDPersistentLogger.shared.log(level: "INFO", message: "Initiating disk scan sweep...")
        let outputJSONPath = getWorkspacePath() + "/scan_results.json"
        let reportMDPath = getWorkspacePath() + "/cleanup_report.md"
        
        Task {
            let (status, output) = await runScript(scriptName: "limpia_defensa.py", args: ["scan", "--output", outputJSONPath, "--report", reportMDPath], elevate: useSudo)
            isScanning = false
            if status == 0 {
                do {
                    let data = try Data(contentsOf: URL(fileURLWithPath: outputJSONPath))
                    let decoded = try JSONDecoder().decode(ScanResults.self, from: data)
                    self.scanResults = decoded
                    self.gdriveConnected = decoded.gdrive_connected
                    
                    if !cleanHasRun || sizeBeforeClean == 0 {
                        sizeBeforeClean = decoded.summary.reclaimable_size
                        sizeAfterClean = decoded.summary.reclaimable_size
                    } else {
                        sizeAfterClean = decoded.summary.reclaimable_size
                    }
                    
                    LDPersistentLogger.shared.log(level: "INFO", message: "Scan parse succeeded. Reclaimable str: \(decoded.summary.reclaimable_str)")
                } catch {
                    LDPersistentLogger.shared.log(level: "ERROR", message: "Failed to parse scan metadata: \(error.localizedDescription)")
                    self.errorMessage = "Failed to parse scan metadata: \(error.localizedDescription)"
                }
            } else {
                LDPersistentLogger.shared.log(level: "ERROR", message: "Scan runner failed with status: \(status)")
                self.errorMessage = "Scan Execution Failed: \(output)"
            }
        }
    }
    
    private func triggerClean() {
        guard !isCleaning else { return }
        
        if encryptBackups && encryptionPassphrase.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            self.errorMessage = "Encryption Passphrase Required: Please enter an AES-256 Passphrase to encrypt your backup."
            return
        }
        
        isCleaning = true
        cleanHasRun = true
        sizeBeforeClean = scanResults?.summary.reclaimable_size ?? 0
        
        let inputJSONPath = getWorkspacePath() + "/scan_results.json"
        let categoriesArg = selectedCategories.joined(separator: ",")
        
        var args = ["clean", "--input", inputJSONPath, "--categories", categoriesArg] + getBackupArgs() + getEncryptionArgs(isClean: true)
        if useSudo {
            args.append("--sudo")
        }
        
        consoleLog = "Pruning started. Staging files to backup target mount first...\n"
        LDPersistentLogger.shared.log(level: "INFO", message: "Executing cleanup for categories: \(categoriesArg)")
        
        Task {
            let (status, output) = await runScript(scriptName: "limpia_defensa.py", args: args, elevate: useSudo)
            isCleaning = false
            consoleLog += output + "\n"
            if status == 0 {
                LDPersistentLogger.shared.log(level: "INFO", message: "Cleanup completed successfully.")
                consoleLog += "✅ Cleanup operation completed successfully!\n"
                triggerScan()
                triggerBackupsList()
            } else {
                LDPersistentLogger.shared.log(level: "ERROR", message: "Clean operation failed: \(output)")
                self.errorMessage = "Clean operation failed: \(output)"
                consoleLog += "❌ Clean failed with exit code \(status)\n"
            }
        }
    }
    
    private func triggerCleanSingle(category: String) {
        guard !isCleaning && runningIndividualTask == nil else { return }
        
        if encryptBackups && encryptionPassphrase.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            self.errorMessage = "Encryption Passphrase Required: Please enter an AES-256 Passphrase to encrypt your backup."
            return
        }
        
        runningIndividualTask = category
        isCleaning = true
        cleanHasRun = true
        sizeBeforeClean = scanResults?.summary.reclaimable_size ?? 0
        
        let inputJSONPath = getWorkspacePath() + "/scan_results.json"
        var args = ["clean", "--input", inputJSONPath, "--categories", category] + getBackupArgs() + getEncryptionArgs(isClean: true)
        if useSudo {
            args.append("--sudo")
        }
        
        consoleLog = "Pruning \(category) started. Staging files to backup target mount first...\n"
        LDPersistentLogger.shared.log(level: "INFO", message: "Executing individual cleanup for category: \(category)")
        
        Task {
            let (status, output) = await runScript(scriptName: "limpia_defensa.py", args: args, elevate: useSudo)
            isCleaning = false
            runningIndividualTask = nil
            consoleLog += output + "\n"
            if status == 0 {
                LDPersistentLogger.shared.log(level: "INFO", message: "Individual cleanup for \(category) completed successfully.")
                consoleLog += "✅ Cleaned category '\(category)' successfully!\n"
                triggerScan()
                triggerBackupsList()
            } else {
                LDPersistentLogger.shared.log(level: "ERROR", message: "Clean operation for \(category) failed: \(output)")
                self.errorMessage = "Clean operation for \(category) failed: \(output)"
                consoleLog += "❌ Clean failed with exit code \(status)\n"
            }
        }
    }
    
    private func triggerQuarantine(filePath: String, pid: Int32) {
        guard !isCleaning else { return }
        
        if encryptBackups && encryptionPassphrase.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            self.errorMessage = "Encryption Passphrase Required: Please enter an AES-256 Passphrase in settings to encrypt quarantine backup."
            return
        }
        
        isCleaning = true
        LDPersistentLogger.shared.log(level: "INFO", message: "Remediating threat process: \(filePath) (PID: \(pid))")
        consoleLog = "Remediating threat process at \(filePath)...\n"
        
        let args = ["quarantine", "--file", filePath, "--pid", "\(pid)"] + getBackupArgs() + getEncryptionArgs(isClean: true)
        
        Task {
            // Remediating running threats requires administrator elevation
            let (status, output) = await runScript(scriptName: "limpia_defensa.py", args: args, elevate: true)
            isCleaning = false
            consoleLog += output + "\n"
            if status == 0 {
                LDPersistentLogger.shared.log(level: "INFO", message: "Quarantine and process termination succeeded.")
                consoleLog += "✅ Remediation completed! Threat terminated and original executable archived.\n"
                triggerThreatScan()
                triggerBackupsList()
            } else {
                LDPersistentLogger.shared.log(level: "ERROR", message: "Remediation failed: \(output)")
                self.errorMessage = "Remediation execution failed: \(output)"
                consoleLog += "❌ Remediation failed with exit code \(status)\n"
            }
        }
    }
    
    private func triggerThreatScan() {
        guard !isThreatScanning else { return }
        isThreatScanning = true
        
        Task {
            let threats = await Task.detached(priority: .userInitiated) {
                QuetzalCore.runActiveScan()
            }.value
            
            self.activeThreats = threats
            self.isThreatScanning = false
        }
    }
    
    private func triggerBackupsList() {
        LDPersistentLogger.shared.log(level: "INFO", message: "Syncing backup sessions...")
        let args = ["list-backups"] + getBackupArgs()
        Task {
            let (status, output) = await runScript(scriptName: "limpia_defensa.py", args: args)
            if status == 0 {
                do {
                    if let data = output.data(using: .utf8) {
                        let decoded = try JSONDecoder().decode(BackupListResponse.self, from: data)
                        self.backups = decoded.backups
                        self.gdriveConnected = decoded.connected
                        LDPersistentLogger.shared.log(level: "INFO", message: "Retrieved \(decoded.backups.count) backup sessions.")
                    }
                } catch {
                    LDPersistentLogger.shared.log(level: "ERROR", message: "Failed to decode backup response: \(error.localizedDescription)")
                }
            }
        }
    }
    
    private func triggerRestore(session: String, path: String) {
        guard !isRestoring else { return }
        
        if encryptBackups && encryptionPassphrase.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            self.errorMessage = "Decryption Passphrase Required: Please enter the AES-256 Passphrase in the settings."
            return
        }
        
        isRestoring = true
        LDPersistentLogger.shared.log(level: "INFO", message: "Triggering file restoration. Session: \(session), Path: \(path)")
        
        let args = ["restore", "--date", session, "--path", path] + getBackupArgs() + getEncryptionArgs(isClean: false)
        Task {
            let (status, output) = await runScript(scriptName: "limpia_defensa.py", args: args, elevate: useSudo)
            isRestoring = false
            if status == 0 {
                LDPersistentLogger.shared.log(level: "INFO", message: "File restoration completed successfully.")
                triggerScan()
                triggerBackupsList()
            } else {
                LDPersistentLogger.shared.log(level: "ERROR", message: "Restore failed: \(output)")
                self.errorMessage = "Restore failed: \(output)"
            }
        }
    }
    
    private func triggerRollback(session: String) {
        guard !isRollingBack else { return }
        
        if encryptBackups && encryptionPassphrase.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            self.errorMessage = "Decryption Passphrase Required: Please enter the AES-256 Passphrase to roll back this session."
            return
        }
        
        isRollingBack = true
        LDPersistentLogger.shared.log(level: "INFO", message: "Triggering session rollback. Session: \(session)")
        consoleLog = "Starting rollback for session \(session)...\n"
        
        let args = ["rollback", "--date", session] + getBackupArgs() + getEncryptionArgs(isClean: false)
        Task {
            let (status, output) = await runScript(scriptName: "limpia_defensa.py", args: args, elevate: useSudo)
            isRollingBack = false
            consoleLog += output + "\n"
            if status == 0 {
                LDPersistentLogger.shared.log(level: "INFO", message: "Rollback completed successfully.")
                consoleLog += "✅ Rollback completed successfully!\n"
                triggerScan()
                triggerBackupsList()
            } else {
                LDPersistentLogger.shared.log(level: "ERROR", message: "Rollback failed: \(output)")
                self.errorMessage = "Rollback failed: \(output)"
                consoleLog += "❌ Rollback failed with exit code \(status)\n"
            }
        }
    }
    
    private func checkMigrationPauseState() {
        isMigrationPaused = FileManager.default.fileExists(atPath: getWorkspacePath() + "/pause.flag")
    }
    
    private func toggleMigrationPause() {
        let flagPath = getWorkspacePath() + "/pause.flag"
        if FileManager.default.fileExists(atPath: flagPath) {
            try? FileManager.default.removeItem(atPath: flagPath)
            isMigrationPaused = false
            LDPersistentLogger.shared.log(level: "INFO", message: "Migration stager resume: deleted pause.flag")
            migrationLog += "▶️ Resumed migration stager...\n"
        } else {
            try? "".write(toFile: flagPath, atomically: true, encoding: .utf8)
            isMigrationPaused = true
            LDPersistentLogger.shared.log(level: "INFO", message: "Migration stager pause: created pause.flag")
            migrationLog += "⏸️ Paused migration stager (waiting for current file to complete staging)...\n"
        }
    }
    
    private func triggerMigration() {
        guard !isMigrating else { return }
        isMigrating = true
        checkMigrationPauseState()
        
        migrationLog = "=== Launching Staged Cloud & Disk Migration ===\n"
        LDPersistentLogger.shared.log(level: "INFO", message: "Starting cloud migration stager script.")
        
        Task {
            let (status, output) = await runScript(scriptName: "cloud_migration_stager.py", args: [])
            isMigrating = false
            migrationLog += output + "\n"
            if status == 0 {
                LDPersistentLogger.shared.log(level: "INFO", message: "Migration stager completed successfully.")
                migrationLog += "✅ Migration staging finished successfully!\n"
            } else {
                LDPersistentLogger.shared.log(level: "ERROR", message: "Migration stager failed: \(output)")
                migrationLog += "❌ Migration stager failed with exit code \(status)\n"
            }
        }
    }
    
    private func startOver() {
        scanResults = nil
        consoleLog = ""
        selectedCategories = ["caches", "logs"]
        errorMessage = nil
        useSudo = false
        advancedMode = false
        encryptBackups = false
        encryptionPassphrase = ""
        sizeBeforeClean = 0
        sizeAfterClean = 0
        cleanHasRun = false
        runningIndividualTask = nil
        LDPersistentLogger.shared.log(level: "INFO", message: "User requested state reset. GUI states starting over.")
    }
}

// ==============================================================================
// 🖼️ UI VIEWS & COMPONENT ELEMENTS
// ==============================================================================
struct NavigationButton: View {
    let tab: NavigationTab
    @Binding var activeTab: NavigationTab
    
    var body: some View {
        Button(action: { activeTab = tab }) {
            HStack {
                Image(systemName: tab.iconName)
                    .font(.headline)
                    .foregroundColor(activeTab == tab ? .green : .secondary)
                    .frame(width: 24, alignment: .center)
                Text(tab.rawValue)
                    .font(.body)
                    .fontWeight(activeTab == tab ? .semibold : .regular)
                Spacer()
            }
            .padding(.vertical, 6)
            .padding(.horizontal, 10)
            .background(activeTab == tab ? Color.green.opacity(0.12) : Color.clear)
            .cornerRadius(8)
        }
        .buttonStyle(.plain)
    }
}

struct DetailRouterView: View {
    let tab: NavigationTab
    @Binding var scanResults: ScanResults?
    @Binding var backups: [BackupSession]
    @Binding var activeThreats: [ThreatProcess]
    
    @Binding var isScanning: Bool
    @Binding var isCleaning: Bool
    @Binding var runningIndividualTask: String?
    @Binding var isThreatScanning: Bool
    @Binding var isRestoring: Bool
    @Binding var gdriveConnected: Bool
    
    @Binding var selectedCategories: Set<String>
    @Binding var consoleLog: String
    @Binding var errorMessage: String?
    @Binding var useSudo: Bool
    
    @Binding var backupType: String
    @Binding var customBackupPath: String
    @Binding var encryptBackups: Bool
    @Binding var encryptionPassphrase: String
    @Binding var advancedMode: Bool
    @Binding var isRollingBack: Bool
    
    @Binding var cleanHasRun: Bool
    @Binding var sizeBeforeClean: Int64
    @Binding var sizeAfterClean: Int64
    
    @Binding var isMigrating: Bool
    @Binding var isMigrationPaused: Bool
    @Binding var migrationLog: String
    
    let triggerScan: () -> Void
    let triggerClean: () -> Void
    let triggerCleanSingle: (String) -> Void
    let triggerQuarantine: (String, Int32) -> Void
    let triggerThreatScan: () -> Void
    let triggerBackupsList: () -> Void
    let triggerRestore: (String, String) -> Void
    let triggerRollback: (String) -> Void
    let triggerMigration: () -> Void
    let toggleMigrationPause: () -> Void
    let checkMigrationPauseState: () -> Void
    let startOver: () -> Void
    
    var body: some View {
        VStack(spacing: 0) {
            // Header bar
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(tab.rawValue)
                        .font(.title)
                        .bold()
                    Text("Limpia-Defensa Core Engine Active")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                Spacer()
                
                // Status pill
                HStack(spacing: 6) {
                    Circle()
                        .fill(gdriveConnected ? Color.green : Color.orange)
                        .frame(width: 8, height: 8)
                    Text(gdriveConnected ? "GDrive Backup Active" : "GDrive Off")
                        .font(.caption)
                        .bold()
                }
                .padding(.vertical, 4)
                .padding(.horizontal, 8)
                .background(Color.white.opacity(0.06))
                .cornerRadius(12)
            }
            .padding(20)
            
            Divider()
            
            // Detail screens
            switch tab {
            case .dashboard:
                DashboardView(
                    scanResults: $scanResults,
                    activeThreats: $activeThreats,
                    backups: $backups,
                    isScanning: $isScanning,
                    cleanHasRun: $cleanHasRun,
                    sizeBeforeClean: $sizeBeforeClean,
                    sizeAfterClean: $sizeAfterClean,
                    triggerScan: triggerScan,
                    startOver: startOver
                )
            case .cleanup:
                CleanupView(
                    scanResults: $scanResults,
                    isScanning: $isScanning,
                    isCleaning: $isCleaning,
                    runningIndividualTask: $runningIndividualTask,
                    selectedCategories: $selectedCategories,
                    useSudo: $useSudo,
                    consoleLog: $consoleLog,
                    advancedMode: $advancedMode,
                    triggerScan: triggerScan,
                    triggerClean: triggerClean,
                    triggerCleanSingle: triggerCleanSingle,
                    startOver: startOver
                )
            case .quetzalCore:
                QuetzalCoreAVView(
                    activeThreats: $activeThreats,
                    isThreatScanning: $isThreatScanning,
                    isCleaning: $isCleaning,
                    triggerThreatScan: triggerThreatScan,
                    triggerQuarantine: triggerQuarantine
                )
            case .backups:
                BackupsView(
                    backups: $backups,
                    isRestoring: $isRestoring,
                    isRollingBack: $isRollingBack,
                    backupType: $backupType,
                    customBackupPath: $customBackupPath,
                    encryptBackups: $encryptBackups,
                    encryptionPassphrase: $encryptionPassphrase,
                    isMigrating: $isMigrating,
                    isMigrationPaused: $isMigrationPaused,
                    migrationLog: $migrationLog,
                    triggerBackupsList: triggerBackupsList,
                    triggerRestore: triggerRestore,
                    triggerRollback: triggerRollback,
                    triggerMigration: triggerMigration,
                    toggleMigrationPause: toggleMigrationPause,
                    checkMigrationPauseState: checkMigrationPauseState
                )
            case .about:
                AboutHelpView()
            }
        }
        .background(Color(NSColor.windowBackgroundColor))
    }
}

// 1. Dashboard View
struct DashboardView: View {
    @Binding var scanResults: ScanResults?
    @Binding var activeThreats: [ThreatProcess]
    @Binding var backups: [BackupSession]
    @Binding var isScanning: Bool
    
    @Binding var cleanHasRun: Bool
    @Binding var sizeBeforeClean: Int64
    @Binding var sizeAfterClean: Int64
    
    let triggerScan: () -> Void
    let startOver: () -> Void
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Main stats widget
                HStack(spacing: 20) {
                    // Storage reclaimed
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Reclaimable SSD Space")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        Text(scanResults?.summary.reclaimable_str ?? "0 B")
                            .font(.system(size: 36, weight: .bold))
                            .foregroundColor(.green)
                        Text("Scanned Caches, Logs, Installers, & Orphans")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.white.opacity(0.04))
                    .cornerRadius(12)
                    
                    // Threat status card
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Security Threat Profile")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        
                        let criticalCount = activeThreats.filter { $0.isCritical }.count
                        if criticalCount > 0 {
                            Text("\(criticalCount) Active Threat\(criticalCount > 1 ? "s" : "")")
                                .font(.system(size: 32, weight: .bold))
                                .foregroundColor(.red)
                            Text("Quetzal Core requires immediate remediation")
                                .font(.caption)
                                .foregroundColor(.red.opacity(0.8))
                        } else {
                            Text("Safe & Signed")
                                .font(.system(size: 32, weight: .bold))
                                .foregroundColor(.green)
                            Text("Active memory processes signed & secure")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.white.opacity(0.04))
                    .cornerRadius(12)
                }
                
                if cleanHasRun {
                    DeltaChangeGraph(sizeBeforeClean: sizeBeforeClean, sizeAfterClean: sizeAfterClean)
                }
                
                // Detailed card
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("Optimiser Scan Summary")
                            .font(.headline)
                        Spacer()
                        
                        HStack(spacing: 12) {
                            if isScanning {
                                ProgressView().scaleEffect(0.6)
                            } else {
                                Button("Start Over", action: startOver)
                                    .buttonStyle(.bordered)
                                
                                Button("Force Rescan", action: triggerScan)
                                    .buttonStyle(.borderedProminent)
                                    .tint(.green.opacity(0.8))
                            }
                        }
                    }
                    .padding(.bottom, 4)
                    
                    if let results = scanResults {
                        HStack {
                            VStack(alignment: .leading, spacing: 6) {
                                Text("Last indexed: \(results.timestamp)")
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                                Text("Google Drive Cloud Backups: \(results.gdrive_connected ? "Connected" : "Disconnected")")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            Spacer()
                        }
                        
                        Divider()
                        
                        VStack(spacing: 8) {
                            CategoryRow(name: "User & System Caches", count: results.categories.caches.count, size: formatBytes(results.categories.caches.reduce(0) { $0 + $1.size }))
                            if let devCaches = results.categories.developer_caches, !devCaches.isEmpty {
                                CategoryRow(name: "Developer Caches (NPM/Gradle/Pods)", count: devCaches.count, size: formatBytes(devCaches.reduce(0) { $0 + $1.size }))
                            }
                            if let aiCaches = results.categories.ai_model_caches, !aiCaches.isEmpty {
                                CategoryRow(name: "AI Models & Weights (HF/Codex)", count: aiCaches.count, size: formatBytes(aiCaches.reduce(0) { $0 + $1.size }))
                            }
                            if let trash = results.categories.trash, !trash.isEmpty {
                                CategoryRow(name: "User Trash Bin", count: trash.count, size: formatBytes(trash.reduce(0) { $0 + $1.size }))
                            }
                            if let browsers = results.categories.browser_caches, !browsers.isEmpty {
                                CategoryRow(name: "Browser Caches (Chrome/Safari)", count: browsers.count, size: formatBytes(browsers.reduce(0) { $0 + $1.size }))
                            }
                            CategoryRow(name: "Log Buffers", count: results.categories.logs.count, size: formatBytes(results.categories.logs.reduce(0) { $0 + $1.size }))
                            CategoryRow(name: "DMG/PKG Installers", count: results.categories.installers.count, size: formatBytes(results.categories.installers.reduce(0) { $0 + $1.size }))
                            CategoryRow(name: "Duplicate Clusters", count: results.categories.duplicates.count, size: formatBytes(results.categories.duplicates.reduce(0) { $0 + $1.size * Int64($1.paths.count - 1) }))
                            CategoryRow(name: "Orphaned App Supports", count: results.categories.orphans.count, size: formatBytes(results.categories.orphans.reduce(0) { $0 + $1.size }))
                            
                            if let vms = results.categories.vms {
                                CategoryRow(name: "Virtual Machines", count: vms.count, size: formatBytes(vms.reduce(0) { $0 + $1.size }))
                            }
                            if let videos = results.categories.videos {
                                CategoryRow(name: "Large Videos (>500MB)", count: videos.count, size: formatBytes(videos.reduce(0) { $0 + $1.size }))
                            }
                            if let photos = results.categories.photos {
                                CategoryRow(name: "Photos & Images", count: photos.count, size: formatBytes(photos.reduce(0) { $0 + $1.size }))
                            }
                            if let archives = results.categories.archives {
                                CategoryRow(name: "Stale Archives", count: archives.count, size: formatBytes(archives.reduce(0) { $0 + $1.size }))
                            }
                        }
                    } else {
                        Text("No scan data loaded yet. Run a system scan.")
                            .foregroundColor(.secondary)
                    }
                }
                .padding()
                .background(Color.white.opacity(0.04))
                .cornerRadius(12)
            }
            .padding(20)
        }
    }
}

struct CategoryRow: View {
    let name: String
    let count: Int
    let size: String
    
    var body: some View {
        HStack {
            Text(name)
                .font(.body)
            Spacer()
            Text("\(count) items")
                .font(.subheadline)
                .foregroundColor(.secondary)
            Text(size)
                .font(.subheadline)
                .bold()
                .foregroundColor(.green)
                .frame(width: 100, alignment: .trailing)
        }
    }
}

// Delta Change Graph View
struct DeltaChangeGraph: View {
    let sizeBeforeClean: Int64
    let sizeAfterClean: Int64
    
    var reclaimedSize: Int64 {
        return max(0, sizeBeforeClean - sizeAfterClean)
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Storage Delta Analysis (Current Session)")
                .font(.headline)
                .foregroundColor(.green)
            
            GeometryReader { geo in
                HStack(spacing: 0) {
                    if reclaimedSize > 0 {
                        Rectangle()
                            .fill(Color.green)
                            .frame(width: geo.size.width * CGFloat(Double(reclaimedSize) / Double(max(1, sizeBeforeClean))))
                    }
                    
                    let remaining = max(0, sizeAfterClean)
                    Rectangle()
                        .fill(Color.white.opacity(0.15))
                        .frame(width: geo.size.width * CGFloat(Double(remaining) / Double(max(1, sizeBeforeClean))))
                }
                .cornerRadius(6)
            }
            .frame(height: 18)
            
            HStack {
                HStack(spacing: 6) {
                    Circle().fill(Color.green).frame(width: 8, height: 8)
                    Text("Reclaimed: \(formatBytes(reclaimedSize))")
                        .font(.caption)
                }
                Spacer()
                HStack(spacing: 6) {
                    Circle().fill(Color.white.opacity(0.3)).frame(width: 8, height: 8)
                    Text("Remaining: \(formatBytes(sizeAfterClean))")
                        .font(.caption)
                }
            }
        }
        .padding()
        .background(Color.white.opacity(0.03))
        .cornerRadius(10)
    }
}

// 2. System Cleanup View
struct CleanupView: View {
    @Binding var scanResults: ScanResults?
    @Binding var isScanning: Bool
    @Binding var isCleaning: Bool
    @Binding var runningIndividualTask: String?
    @Binding var selectedCategories: Set<String>
    @Binding var useSudo: Bool
    @Binding var consoleLog: String
    @Binding var advancedMode: Bool
    
    let triggerScan: () -> Void
    let triggerClean: () -> Void
    let triggerCleanSingle: (String) -> Void
    let startOver: () -> Void
    
    private func getCategorySizeStr(id: String) -> String? {
        guard let results = scanResults else { return nil }
        let bytes: Int64
        switch id {
        case "caches":
            bytes = results.categories.caches.reduce(0) { $0 + $1.size }
        case "developer_caches":
            bytes = results.categories.developer_caches?.reduce(0) { $0 + $1.size } ?? 0
        case "ai_model_caches":
            bytes = results.categories.ai_model_caches?.reduce(0) { $0 + $1.size } ?? 0
        case "trash":
            bytes = results.categories.trash?.reduce(0) { $0 + $1.size } ?? 0
        case "browser_caches":
            bytes = results.categories.browser_caches?.reduce(0) { $0 + $1.size } ?? 0
        case "logs":
            bytes = results.categories.logs.reduce(0) { $0 + $1.size }
        case "installers":
            bytes = results.categories.installers.reduce(0) { $0 + $1.size }
        case "duplicates":
            bytes = results.categories.duplicates.reduce(0) { $0 + $1.size * Int64($1.paths.count - 1) }
        case "orphans":
            bytes = results.categories.orphans.reduce(0) { $0 + $1.size }
        case "vms":
            bytes = results.categories.vms?.reduce(0) { $0 + $1.size } ?? 0
        case "videos":
            bytes = results.categories.videos?.reduce(0) { $0 + $1.size } ?? 0
        case "photos":
            bytes = results.categories.photos?.reduce(0) { $0 + $1.size } ?? 0
        case "archives":
            bytes = results.categories.archives?.reduce(0) { $0 + $1.size } ?? 0
        default:
            return nil
        }
        return formatBytes(bytes)
    }
    
    var body: some View {
        HSplitView {
            // Options Panel
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    
                    // 1. Advanced Mode & Category Selection
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Text("Advanced Mode")
                                .font(.headline)
                            Spacer()
                            Toggle("", isOn: $advancedMode)
                                .toggleStyle(SwitchToggleStyle(tint: .green))
                        }
                        
                        Divider()
                        
                        Text("Categories to Optimize")
                            .font(.subheadline)
                            .bold()
                            .foregroundColor(.secondary)
                        
                        VStack(alignment: .leading, spacing: 8) {
                            CategoryCheckbox(
                                id: "caches", 
                                label: "System & User Caches", 
                                description: "User ~/Library/Caches and system cache data", 
                                sizeStr: getCategorySizeStr(id: "caches"), 
                                selected: $selectedCategories, 
                                isCleaning: isCleaning && runningIndividualTask == "caches", 
                                onCleanSingle: { triggerCleanSingle("caches") }
                            )
                            CategoryCheckbox(
                                id: "developer_caches", 
                                label: "Developer Build Caches", 
                                description: "NPM, Gradle, CocoaPods, and Homebrew download caches", 
                                sizeStr: getCategorySizeStr(id: "developer_caches"), 
                                selected: $selectedCategories, 
                                isCleaning: isCleaning && runningIndividualTask == "developer_caches", 
                                onCleanSingle: { triggerCleanSingle("developer_caches") }
                            )
                            CategoryCheckbox(
                                id: "ai_model_caches", 
                                label: "AI Models & Weights", 
                                description: "HuggingFace, Codex runtimes, and local model weights", 
                                sizeStr: getCategorySizeStr(id: "ai_model_caches"), 
                                selected: $selectedCategories, 
                                isCleaning: isCleaning && runningIndividualTask == "ai_model_caches", 
                                onCleanSingle: { triggerCleanSingle("ai_model_caches") }
                            )
                            CategoryCheckbox(
                                id: "trash", 
                                label: "Trash Bin", 
                                description: "Files residing in ~/.Trash", 
                                sizeStr: getCategorySizeStr(id: "trash"), 
                                selected: $selectedCategories, 
                                isCleaning: isCleaning && runningIndividualTask == "trash", 
                                onCleanSingle: { triggerCleanSingle("trash") }
                            )
                            CategoryCheckbox(
                                id: "browser_caches", 
                                label: "Browser Caches", 
                                description: "Chrome, Safari, Edge, and Arc disk caches", 
                                sizeStr: getCategorySizeStr(id: "browser_caches"), 
                                selected: $selectedCategories, 
                                isCleaning: isCleaning && runningIndividualTask == "browser_caches", 
                                onCleanSingle: { triggerCleanSingle("browser_caches") }
                            )
                            CategoryCheckbox(
                                id: "logs", 
                                label: "Logs", 
                                description: "Log buffers, diagnostic reports, and Unix logs", 
                                sizeStr: getCategorySizeStr(id: "logs"), 
                                selected: $selectedCategories, 
                                isCleaning: isCleaning && runningIndividualTask == "logs", 
                                onCleanSingle: { triggerCleanSingle("logs") }
                            )
                            CategoryCheckbox(
                                id: "installers", 
                                label: "Leftover Installers", 
                                description: "DMG and PKG packages in Downloads/Desktop", 
                                sizeStr: getCategorySizeStr(id: "installers"), 
                                selected: $selectedCategories, 
                                isCleaning: isCleaning && runningIndividualTask == "installers", 
                                onCleanSingle: { triggerCleanSingle("installers") }
                            )
                            
                            // Stale App Data (Orphans) and Duplicates require Advanced Mode
                            CategoryCheckbox(
                                id: "orphans", 
                                label: "Orphaned App Data", 
                                description: "Application Support folders of deleted apps", 
                                sizeStr: getCategorySizeStr(id: "orphans"), 
                                selected: $selectedCategories, 
                                isCleaning: isCleaning && runningIndividualTask == "orphans", 
                                onCleanSingle: { triggerCleanSingle("orphans") }
                            )
                            .disabled(!advancedMode)
                            .opacity(advancedMode ? 1.0 : 0.5)
                            
                            CategoryCheckbox(
                                id: "duplicates", 
                                label: "Prune Duplicate Files", 
                                description: "Preserves one copy of identical duplicates", 
                                sizeStr: getCategorySizeStr(id: "duplicates"), 
                                selected: $selectedCategories, 
                                isCleaning: isCleaning && runningIndividualTask == "duplicates", 
                                onCleanSingle: { triggerCleanSingle("duplicates") }
                            )
                            .disabled(!advancedMode)
                            .opacity(advancedMode ? 1.0 : 0.5)
                        }
                    }
                    .padding()
                    .background(Color.white.opacity(0.02))
                    .cornerRadius(8)
                    
                    // 2. Selective Media Migration
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Selective Media Migration")
                            .font(.subheadline)
                            .bold()
                            .foregroundColor(.secondary)
                        
                        VStack(alignment: .leading, spacing: 8) {
                            CategoryCheckbox(
                                id: "vms", 
                                label: "Virtual Machines", 
                                description: "Move VMs (.qcow2, .utm, .pvm, .vdi, .vmdk)", 
                                sizeStr: getCategorySizeStr(id: "vms"), 
                                selected: $selectedCategories, 
                                isCleaning: isCleaning && runningIndividualTask == "vms", 
                                onCleanSingle: { triggerCleanSingle("vms") }
                            )
                            CategoryCheckbox(
                                id: "videos", 
                                label: "Large Videos (>500MB)", 
                                description: "Move video files to staging target", 
                                sizeStr: getCategorySizeStr(id: "videos"), 
                                selected: $selectedCategories, 
                                isCleaning: isCleaning && runningIndividualTask == "videos", 
                                onCleanSingle: { triggerCleanSingle("videos") }
                            )
                            CategoryCheckbox(
                                id: "photos", 
                                label: "Photos & Images", 
                                description: "Move photo and picture folders", 
                                sizeStr: getCategorySizeStr(id: "photos"), 
                                selected: $selectedCategories, 
                                isCleaning: isCleaning && runningIndividualTask == "photos", 
                                onCleanSingle: { triggerCleanSingle("photos") }
                            )
                            CategoryCheckbox(
                                id: "archives", 
                                label: "Stale Archives", 
                                description: "Move archive packages (.zip, .tar.gz)", 
                                sizeStr: getCategorySizeStr(id: "archives"), 
                                selected: $selectedCategories, 
                                isCleaning: isCleaning && runningIndividualTask == "archives", 
                                onCleanSingle: { triggerCleanSingle("archives") }
                            )
                        }
                    }
                    .padding()
                    .background(Color.white.opacity(0.02))
                    .cornerRadius(8)
                    
                    // 3. Live Risk Assessment Widget
                    LiveRiskWidget(selectedCategories: selectedCategories, useSudo: useSudo, advancedMode: advancedMode)
                    
                    // 4. Elevated Mode & Execution
                    VStack(alignment: .leading, spacing: 10) {
                        if (selectedCategories.contains("caches") || selectedCategories.contains("logs")) && !useSudo {
                            HStack(spacing: 6) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .foregroundColor(.orange)
                                Text("System-level caches/logs require Elevated Mode to clean.")
                                    .font(.caption)
                                    .foregroundColor(.orange)
                            }
                            .padding(.bottom, 4)
                        }
                        
                        Toggle("Elevated Mode (--sudo)", isOn: $useSudo)
                            .toggleStyle(.checkbox)
                            .disabled(!advancedMode)
                            .opacity(advancedMode ? 1.0 : 0.5)
                            .help("Required to clean system folders (/Library/Caches, /var/log). You must run the app with sudo permissions.")
                        
                        HStack(spacing: 12) {
                            if isScanning {
                                ProgressView().scaleEffect(0.6)
                            } else {
                                Button("Start Over", action: startOver)
                                Button("Scan Space", action: triggerScan)
                                    .controlSize(.large)
                            }
                            
                            Spacer()
                            
                            if isCleaning && runningIndividualTask == nil {
                                ProgressView().scaleEffect(0.6)
                            } else {
                                Button("Optimize Selected", action: triggerClean)
                                    .controlSize(.large)
                                    .tint(.green)
                                    .buttonStyle(.borderedProminent)
                                    .disabled(selectedCategories.isEmpty || isCleaning)
                            }
                        }
                    }
                    .padding(.top, 10)
                }
                .padding(20)
            }
            .frame(minWidth: 320, maxWidth: 420)
            
            // Console Outputs
            VStack(alignment: .leading, spacing: 10) {
                Text("Action Activity Log")
                    .font(.headline)
                    .padding(.horizontal, 20)
                    .padding(.top, 20)
                
                ScrollView {
                    Text(consoleLog.isEmpty ? "No clean actions run yet.\nNote: limpa-defensa automatically stages backups before deletion. Configure backup staging target under Backup & Restore." : consoleLog)
                        .font(.system(.body, design: .monospaced))
                        .foregroundColor(consoleLog.isEmpty ? .secondary : .primary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding()
                }
                .background(Color.black.opacity(0.2))
                .cornerRadius(8)
                .padding([.horizontal, .bottom], 20)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}

struct LiveRiskWidget: View {
    let selectedCategories: Set<String>
    let useSudo: Bool
    let advancedMode: Bool
    
    var riskLevel: String {
        if selectedCategories.isEmpty {
            return "NONE"
        }
        if useSudo {
            return "HIGH"
        }
        if selectedCategories.contains("orphans") || selectedCategories.contains("duplicates") {
            return advancedMode ? "HIGH" : "MEDIUM"
        }
        if selectedCategories.contains("vms") || selectedCategories.contains("videos") {
            return "MEDIUM"
        }
        return "LOW"
    }
    
    var riskColor: Color {
        switch riskLevel {
        case "HIGH": return .red
        case "MEDIUM": return .orange
        case "LOW": return .green
        default: return .secondary
        }
    }
    
    var riskDescription: String {
        switch riskLevel {
        case "HIGH":
            return "Warning: High risk operations selected. System folders or system configuration files might be modified."
        case "MEDIUM":
            return "Caution: Medium risk. Cleanups will relocate large archives, videos, or virtual machines."
        case "LOW":
            return "Safe: Low risk operations. Pruning temporary caches and diagnostic log buffers only."
        default:
            return "Select categories to begin risk assessment."
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Operational Risk Level")
                    .font(.caption)
                    .bold()
                    .foregroundColor(.secondary)
                Spacer()
                Text(riskLevel)
                    .font(.caption)
                    .bold()
                    .foregroundColor(riskColor)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(riskColor.opacity(0.12))
                    .cornerRadius(4)
            }
            
            Text(riskDescription)
                .font(.caption2)
                .foregroundColor(.secondary)
                .lineLimit(nil)
            
            if !selectedCategories.isEmpty {
                Divider()
                Text("Safety Checks Passed:")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(.secondary)
                
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 4) {
                        Image(systemName: "checkmark.circle.fill").foregroundColor(.green).font(.system(size: 10))
                        Text("Staging Backup is Gated").font(.system(size: 9)).foregroundColor(.secondary)
                    }
                    if useSudo {
                        HStack(spacing: 4) {
                            Image(systemName: "exclamationmark.triangle.fill").foregroundColor(.orange).font(.system(size: 10))
                            Text("Requires Admin elevation").font(.system(size: 9)).foregroundColor(.orange)
                        }
                    }
                }
            }
        }
        .padding()
        .background(riskColor.opacity(0.04))
        .cornerRadius(8)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(riskColor.opacity(0.2), lineWidth: 1)
        )
    }
}

struct CategoryCheckbox: View {
    let id: String
    let label: String
    let description: String
    let sizeStr: String?
    @Binding var selected: Set<String>
    var isCleaning: Bool
    var onCleanSingle: (() -> Void)?
    
    var body: some View {
        HStack(alignment: .center) {
            Toggle("", isOn: Binding<Bool>(
                get: { selected.contains(id) },
                set: {
                    if $0 {
                        selected.insert(id)
                    } else {
                        selected.remove(id)
                    }
                }
            ))
            .toggleStyle(.checkbox)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .bold()
                Text(description)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            if let size = sizeStr {
                Text(size)
                    .font(.caption)
                    .foregroundColor(.green)
                    .bold()
                    .padding(.trailing, 8)
            }
            
            if let onClean = onCleanSingle {
                Button(action: onClean) {
                    if isCleaning {
                        ProgressView().scaleEffect(0.4)
                            .frame(width: 32, height: 16)
                    } else {
                        Text("Clean")
                            .font(.caption2)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(Color.green.opacity(0.15))
                            .foregroundColor(.green)
                            .cornerRadius(4)
                    }
                }
                .buttonStyle(PlainButtonStyle())
                .disabled(isCleaning)
            }
        }
        .padding(.vertical, 4)
    }
}

// 3. Quetzal Core AV View
struct QuetzalCoreAVView: View {
    @Binding var activeThreats: [ThreatProcess]
    @Binding var isThreatScanning: Bool
    @Binding var isCleaning: Bool
    
    let triggerThreatScan: () -> Void
    let triggerQuarantine: (String, Int32) -> Void
    
    var body: some View {
        VStack(spacing: 0) {
            // Stats summary
            HStack {
                let critical = activeThreats.filter { $0.isCritical }.count
                let warning = activeThreats.filter { !$0.isCritical }.count
                
                HStack(spacing: 20) {
                    ThreatSummaryMetric(title: "Critical Anomalies", count: critical, color: .red)
                    ThreatSummaryMetric(title: "Suspicious Actions", count: warning, color: .orange)
                    ThreatSummaryMetric(title: "Unsigned Process Vectors", count: activeThreats.filter { !$0.isSigned }.count, color: .yellow)
                }
                
                Spacer()
                
                if isThreatScanning {
                    ProgressView().scaleEffect(0.6)
                } else {
                    Button(action: triggerThreatScan) {
                        Label("Instant Memory Audit", systemImage: "bolt.fill")
                            .padding(.vertical, 6)
                            .padding(.horizontal, 12)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.green)
                }
            }
            .padding(20)
            
            Divider()
            
            // Processes Table
            if activeThreats.isEmpty {
                VStack(spacing: 12) {
                    Spacer()
                    Image(systemName: "checkmark.shield.fill")
                        .font(.system(size: 60))
                        .foregroundColor(.green)
                    Text("No anomalies detected in running memory processes.")
                        .font(.headline)
                    Text("All scanned user processes are code-signed and verified.")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    Spacer()
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List(activeThreats) { threat in
                    HStack(alignment: .center, spacing: 16) {
                        Image(systemName: threat.isCritical ? "exclamationmark.octagon.fill" : "exclamationmark.triangle.fill")
                            .font(.system(size: 24))
                            .foregroundColor(threat.isCritical ? .red : .orange)
                            .frame(width: 32)
                        
                        VStack(alignment: .leading, spacing: 4) {
                            HStack {
                                Text(threat.name)
                                    .bold()
                                    .font(.body)
                                Text("PID: \(threat.pid)")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                    .padding(.horizontal, 6)
                                    .background(Color.white.opacity(0.08))
                                    .cornerRadius(4)
                            }
                            
                            Text(threat.path)
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                                .truncationMode(.middle)
                            
                            Text(threat.reason)
                                .font(.subheadline)
                                .bold()
                                .foregroundColor(threat.isCritical ? .red : .orange)
                        }
                        
                        Spacer()
                        
                        // Status badges
                        VStack(alignment: .trailing, spacing: 4) {
                            StatusBadge(text: threat.isSigned ? "SIGNED" : "UNSIGNED", color: threat.isSigned ? .green : .red)
                            if threat.isDeletedOnLaunch {
                                StatusBadge(text: "DELETED ON DISK", color: .red)
                            }
                            if threat.hasSockets {
                                StatusBadge(text: "PORT OPEN", color: .yellow)
                            }
                        }
                        .frame(width: 120, alignment: .trailing)
                        
                        Button(action: {
                            triggerQuarantine(threat.path, threat.pid)
                        }) {
                            Text("Remediate")
                                .font(.caption2)
                                .bold()
                                .foregroundColor(.red)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Color.red.opacity(0.15))
                                .cornerRadius(4)
                        }
                        .buttonStyle(PlainButtonStyle())
                        .disabled(isCleaning)
                    }
                    .padding(.vertical, 6)
                }
                .listStyle(PlainListStyle())
            }
        }
    }
}

struct ThreatSummaryMetric: View {
    let title: String
    let count: Int
    let color: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
            Text("\(count)")
                .font(.title2)
                .bold()
                .foregroundColor(count > 0 ? color : .secondary)
        }
    }
}

struct StatusBadge: View {
    let text: String
    let color: Color
    
    var body: some View {
        Text(text)
            .font(.system(size: 9, weight: .bold))
            .foregroundColor(color)
            .padding(.vertical, 2)
            .padding(.horizontal, 6)
            .background(color.opacity(0.12))
            .cornerRadius(4)
            .overlay(
                RoundedRectangle(cornerRadius: 4)
                    .stroke(color.opacity(0.3), lineWidth: 1)
            )
    }
}

// 4. Backups View
struct BackupsView: View {
    @Binding var backups: [BackupSession]
    @Binding var isRestoring: Bool
    @Binding var isRollingBack: Bool
    
    @Binding var backupType: String
    @Binding var customBackupPath: String
    @Binding var encryptBackups: Bool
    @Binding var encryptionPassphrase: String
    
    @Binding var isMigrating: Bool
    @Binding var isMigrationPaused: Bool
    @Binding var migrationLog: String
    
    let triggerBackupsList: () -> Void
    let triggerRestore: (String, String) -> Void
    let triggerRollback: (String) -> Void
    let triggerMigration: () -> Void
    let toggleMigrationPause: () -> Void
    let checkMigrationPauseState: () -> Void
    
    @State private var selectedSubTab = 0
    @State private var selectedSession: BackupSession? = nil
    
    var body: some View {
        VStack(spacing: 0) {
            Picker("", selection: $selectedSubTab) {
                Text("Backup Config & Migration").tag(0)
                Text("Timeline & Restore").tag(1)
            }
            .pickerStyle(SegmentedPickerStyle())
            .padding([.horizontal, .top], 20)
            
            Divider()
                .padding(.top, 10)
            
            if selectedSubTab == 0 {
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        // 1. Backup Target Selection
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Backup Staging Target")
                                .font(.headline)
                                .foregroundColor(.secondary)
                            
                            Picker("", selection: $backupType) {
                                Text("Secure Cloud").tag("cloud")
                                Text("Physical Drive").tag("local")
                                Text("Network Share").tag("network")
                            }
                            .pickerStyle(SegmentedPickerStyle())
                            
                            if backupType == "cloud" {
                                Text("Stages files securely to your Google Drive File Provider mount path.")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            } else {
                                VStack(alignment: .leading, spacing: 6) {
                                    Text(backupType == "local" ? "Physical Mount Path" : "Network Mount Path")
                                        .font(.caption)
                                        .bold()
                                    HStack {
                                        TextField("/Volumes/backup_disk", text: $customBackupPath)
                                            .textFieldStyle(RoundedBorderTextFieldStyle())
                                        Button("Browse...") {
                                            let panel = NSOpenPanel()
                                            panel.canChooseFiles = false
                                            panel.canChooseDirectories = true
                                            panel.allowsMultipleSelection = false
                                            if panel.runModal() == .OK {
                                                customBackupPath = panel.url?.path ?? ""
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        .padding()
                        .background(Color.white.opacity(0.02))
                        .cornerRadius(8)
                        
                        // 2. Security & Encryption Options
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                Text("Client-Side Encryption")
                                    .font(.headline)
                                    .foregroundColor(.secondary)
                                Spacer()
                                Toggle("", isOn: $encryptBackups)
                                    .toggleStyle(SwitchToggleStyle(tint: .green))
                            }
                            
                            if encryptBackups {
                                VStack(alignment: .leading, spacing: 6) {
                                    Text("AES-256 Passphrase")
                                        .font(.caption)
                                        .bold()
                                    SecureField("Required for encryption/decryption", text: $encryptionPassphrase)
                                        .textFieldStyle(RoundedBorderTextFieldStyle())
                                    Text("⚠️ Write down this passphrase. If lost, backups cannot be recovered or rolled back.")
                                        .font(.system(size: 10))
                                        .foregroundColor(.orange)
                                }
                            }
                        }
                        .padding()
                        .background(Color.white.opacity(0.02))
                        .cornerRadius(8)
                        
                        // 3. Cloud & Disk Migration Stager
                        VStack(alignment: .leading, spacing: 12) {
                            Text("System Cloud & Disk Migration")
                                .font(.headline)
                            Text("Performs deep system sweep to migrate virtual machines, archives, large videos, and images off local disk storage onto the target backup staging mount.")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            
                            HStack(spacing: 12) {
                                if isMigrating {
                                    Button(action: toggleMigrationPause) {
                                        Label(isMigrationPaused ? "Resume Migration" : "Pause Migration", systemImage: isMigrationPaused ? "play.fill" : "pause.fill")
                                    }
                                } else {
                                    Button(action: triggerMigration) {
                                        Label("Start Staged Migration", systemImage: "arrow.triangle.2.circlepath")
                                    }
                                    .buttonStyle(.borderedProminent)
                                    .tint(.green)
                                }
                            }
                            
                            VStack(alignment: .leading, spacing: 6) {
                                Text("Migration Status & Logs:")
                                    .font(.subheadline)
                                    .bold()
                                ScrollView {
                                    Text(migrationLog.isEmpty ? "Staging engine idle. Start migration to view live activity." : migrationLog)
                                        .font(.system(.body, design: .monospaced))
                                        .foregroundColor(migrationLog.isEmpty ? .secondary : .primary)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .padding()
                                }
                                .background(Color.black.opacity(0.2))
                                .cornerRadius(8)
                                .frame(height: 180)
                            }
                        }
                        .padding()
                        .background(Color.white.opacity(0.02))
                        .cornerRadius(8)
                    }
                    .padding(20)
                }
            } else {
                HSplitView {
                    // Session Timeline List
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Text("Backup Session Timeline")
                                .font(.headline)
                            Spacer()
                            Button(action: triggerBackupsList) {
                                Image(systemName: "arrow.clockwise")
                            }
                            .buttonStyle(.plain)
                        }
                        .padding(.horizontal, 16)
                        .padding(.top, 16)
                        
                        if backups.isEmpty {
                            Spacer()
                            Text("No staging sessions indexed.")
                                .foregroundColor(.secondary)
                                .padding()
                            Spacer()
                        } else {
                            List(backups) { backup in
                                Button(action: { selectedSession = backup }) {
                                    VStack(alignment: .leading, spacing: 6) {
                                        HStack {
                                            Text(backup.session)
                                                .bold()
                                                .foregroundColor(selectedSession?.session == backup.session ? .green : .primary)
                                            Spacer()
                                            if backup.encrypted == true {
                                                Image(systemName: "lock.fill")
                                                    .font(.caption)
                                                    .foregroundColor(.orange)
                                            }
                                        }
                                        HStack {
                                            Text("\(backup.file_count) files")
                                            Text("•")
                                            Text(backup.size_str)
                                        }
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                    }
                                    .padding(8)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .background(selectedSession?.session == backup.session ? Color.green.opacity(0.08) : Color.clear)
                                    .cornerRadius(6)
                                }
                                .buttonStyle(.plain)
                            }
                            .listStyle(PlainListStyle())
                        }
                    }
                    .frame(minWidth: 250, maxWidth: 320)
                    .frame(maxHeight: .infinity)
                    
                    // Session Detail / Restorations
                    VStack(alignment: .leading, spacing: 16) {
                        if let session = selectedSession {
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Session: \(session.session)")
                                        .font(.title3)
                                        .bold()
                                    
                                    HStack(spacing: 8) {
                                        Text("Categories backup: \(session.categories.joined(separator: ", "))")
                                        if session.encrypted == true {
                                            Text("🔒 Encrypted")
                                                .font(.caption)
                                                .bold()
                                                .foregroundColor(.orange)
                                                .padding(.horizontal, 6)
                                                .padding(.vertical, 2)
                                                .background(Color.orange.opacity(0.15))
                                                .cornerRadius(4)
                                        }
                                    }
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                                }
                                Spacer()
                                
                                if isRollingBack {
                                    ProgressView().scaleEffect(0.6)
                                } else {
                                    Button(action: {
                                        triggerRollback(session.session)
                                    }) {
                                        Label("Rollback Session", systemImage: "arrow.uturn.backward")
                                    }
                                    .tint(.orange)
                                    .buttonStyle(.borderedProminent)
                                }
                            }
                            .padding([.horizontal, .top], 20)
                            
                            Divider()
                            
                            // Selective restore instructions
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Staging Restore Operations")
                                    .font(.headline)
                                Text("Provide the absolute original file path you wish to restore from this session directory.")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            .padding(.horizontal, 20)
                            
                            RestoreInputForm(session: session.session, isRestoring: $isRestoring, triggerRestore: triggerRestore)
                                .padding(.horizontal, 20)
                            
                            Spacer()
                        } else {
                            Spacer()
                            VStack(spacing: 12) {
                                Image(systemName: "clock.arrow.2.circlepath")
                                    .font(.system(size: 40))
                                    .foregroundColor(.secondary)
                                Text("Select a backup session from the timeline to perform restorations.")
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                                    .multilineTextAlignment(.center)
                                    .padding(.horizontal, 40)
                            }
                            .frame(maxWidth: .infinity, alignment: .center)
                            Spacer()
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
        }
        .onAppear {
            checkMigrationPauseState()
        }
    }
}

struct RestoreInputForm: View {
    let session: String
    @Binding var isRestoring: Bool
    let triggerRestore: (String, String) -> Void
    
    @State private var restorePath: String = ""
    @State private var successAlert = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            TextField("Original file path (e.g. /Users/xavasena/Downloads/file.dmg)", text: $restorePath)
                .textFieldStyle(RoundedBorderTextFieldStyle())
                .frame(maxWidth: .infinity)
            
            HStack {
                Spacer()
                if isRestoring {
                    ProgressView().scaleEffect(0.6)
                } else {
                    Button("Restore File/Folder", action: {
                        let path = restorePath.trimmingCharacters(in: .whitespacesAndNewlines)
                        if !path.isEmpty {
                            triggerRestore(session, path)
                            successAlert = true
                        }
                    })
                    .buttonStyle(.borderedProminent)
                    .tint(.green)
                    .disabled(restorePath.isEmpty)
                }
            }
            
            if successAlert {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    Text("Restore instruction sent successfully!")
                        .foregroundColor(.green)
                }
                .font(.subheadline)
                .padding(.top, 4)
                .onAppear {
                    Task {
                        try? await Task.sleep(nanoseconds: 4_000_000_000)
                        successAlert = false
                    }
                }
            }
        }
        .padding()
        .background(Color.white.opacity(0.02))
        .cornerRadius(8)
    }
}

// 5. About & Help View
struct AboutHelpView: View {
    @State private var innerTab = 0
    @State private var logContent = "Loading log stream..."
    
    var body: some View {
        VStack(spacing: 0) {
            Picker("", selection: $innerTab) {
                Text("About").tag(0)
                Text("Manual & Help").tag(1)
                Text("Licensing").tag(2)
                Text("Active Engine Logs").tag(3)
            }
            .pickerStyle(SegmentedPickerStyle())
            .padding(.horizontal, 20)
            .padding(.vertical, 10)
            
            Divider()
            
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    switch innerTab {
                    case 0:
                        AboutPanel()
                    case 1:
                        HelpPanel()
                    case 2:
                        LicensePanel()
                    default:
                        LogPanel(logContent: $logContent)
                    }
                }
                .padding(20)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .background(Color.black.opacity(0.12))
        }
        .onAppear {
            refreshLogs()
        }
        .onChange(of: innerTab) { oldVal, newVal in
            if newVal == 3 {
                refreshLogs()
            }
        }
    }
    
    private func refreshLogs() {
        logContent = LDPersistentLogger.shared.readLogs()
    }
}

struct AboutPanel: View {
    var body: some View {
        VStack(alignment: .center, spacing: 15) {
            Spacer().frame(height: 10)
            Image(systemName: "shield.righthalf.filled")
                .font(.system(size: 80))
                .foregroundColor(.green)
                .padding(.bottom, 5)
            
            Text("Limpia-Defensa macOS")
                .font(.title2)
                .bold()
            
            Text("Version 1.2.0")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            Text("Built-in high-performance Quetzal Core Active Memory & Socket Audit Engine. Non-destructive staging-safety pipeline backups via customizable target mount paths and client-side encryption.")
                .multilineTextAlignment(.center)
                .font(.body)
                .foregroundColor(.secondary)
                .padding(.horizontal, 30)
            
            Divider().padding(.vertical, 10)
            
            VStack(spacing: 8) {
                Text("Sandbox Code Sign: \(getSelfSignatureStatus())")
                    .font(.caption)
                    .bold()
                    .foregroundColor(.secondary)
                
                Text("Designed and Developed by Advanced Coding Agents")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text("Copyright © 2026. All rights reserved.")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            Spacer()
        }
        .frame(maxWidth: .infinity, alignment: .center)
    }
    
    func getSelfSignatureStatus() -> String {
        let path = Bundle.main.executablePath ?? CommandLine.arguments[0]
        let url = URL(fileURLWithPath: path)
        var staticCode: SecStaticCode?
        let status = SecStaticCodeCreateWithPath(url as CFURL, [], &staticCode)
        if status == errSecSuccess, let code = staticCode {
            let validityStatus = SecStaticCodeCheckValidity(code, SecCSFlags(rawValue: 0), nil)
            if validityStatus == errSecSuccess {
                return "VERIFIED (Signed Code Identity)"
            } else {
                return "UNSIGNED (Developer Mode / Sandbox Gated)"
            }
        }
        return "UNKNOWN"
    }
}

struct HelpPanel: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("System Manual & Operational Guidance")
                .font(.headline)
                .foregroundColor(.green)
            
            Group {
                HelpSection(title: "1. Staging Target Configuration", bodyText: "Configure your backup staging target under System Cleanup or Backup & Restore. Secure Cloud routes encrypted files to Google Drive, Physical Drive target directories on USB volumes (e.g., /Volumes/USB_Backup), and Network Share paths connect to local NAS mount points.")
                
                HelpSection(title: "2. Mounting SMB Network Shares", bodyText: "To mount an SMB network drive in macOS: open Finder, press Cmd+K, enter 'smb://server-ip/share-name', authenticate, and map it. Ensure the mount directory (typically in /Volumes/) is specified as the backup target path.")
                
                HelpSection(title: "3. Ejecting Physical Targets Safely", bodyText: "Always eject physical USB staging drives via macOS Finder or the 'diskutil eject' command before disconnecting them. This ensures file buffers are fully flushed and manifest checksums are completely written.")
                
                HelpSection(title: "4. Client-Side AES-256 Encryption", bodyText: "By enabling Client-Side Encryption, staged backups are compressed and encrypted locally before sync. File names are obfuscated using a SHA-256 hash of their original path to hide metadata. The manifest catalog is similarly encrypted. Restore operations will prompt for the matching passphrase.")
                
                HelpSection(title: "5. Quetzal Core Active Auditing", bodyText: "Quetzal Core is an in-memory process sweeper. It maps PIDs, resolves execution paths, and audits code signatures using macOS APIs. It detects deleted-on-launch executables and active remote sockets, flagging anomalies in real-time.")
            }
        }
    }
}

struct HelpSection: View {
    let title: String
    let bodyText: String
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.subheadline)
                .bold()
            Text(bodyText)
                .font(.body)
                .foregroundColor(.secondary)
        }
        .padding(.bottom, 6)
    }
}

struct LicensePanel: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Software License Agreement")
                .font(.headline)
                .foregroundColor(.green)
            
            Text("MIT License")
                .font(.subheadline)
                .bold()
            
            Text("""
Copyright (c) 2026 Limpia-Defensa Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy \
of this software and associated documentation files (the "Software"), to deal \
in the Software without restriction, including without limitation the rights \
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell \
copies of the Software, and to permit persons to whom the Software is \
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all \
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR \
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, \
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE \
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER \
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, \
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE \
SOFTWARE.
""")
            .font(.system(.body, design: .monospaced))
            .foregroundColor(.secondary)
            .padding(10)
            .background(Color.white.opacity(0.02))
            .cornerRadius(6)
        }
    }
}

struct LogPanel: View {
    @Binding var logContent: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Persistent Engine Logs")
                    .font(.headline)
                    .foregroundColor(.green)
                Spacer()
                Button(action: {
                    logContent = LDPersistentLogger.shared.readLogs()
                }) {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
                Button(action: {
                    LDPersistentLogger.shared.clearLogs()
                    logContent = LDPersistentLogger.shared.readLogs()
                }) {
                    Label("Clear Logs", systemImage: "trash")
                }
            }
            
            Text("File location: ~/Library/Logs/LimpiaDefensa.log")
                .font(.caption)
                .foregroundColor(.secondary)
            
            ScrollView {
                Text(logContent)
                    .font(.system(.body, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
            }
            .frame(height: 320)
            .background(Color.black.opacity(0.4))
            .cornerRadius(8)
        }
    }
}
