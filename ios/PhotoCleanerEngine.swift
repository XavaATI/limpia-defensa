import Foundation
import Photos
import UIKit

struct DuplicateGroup: Identifiable {
    let id = UUID()
    let representativeAsset: PHAsset
    let duplicates: [PHAsset]
    var totalSize: Int64
}

class PhotoCleanerEngine: ObservableObject {
    @Published var isScanning = false
    @Published var authorizationStatus: PHAuthorizationStatus = .notDetermined
    
    // Scanned categories
    @Published var duplicates: [DuplicateGroup] = []
    @Published var screenshots: [PHAsset] = []
    @Published var largeVideos: [PHAsset] = []
    @Published var scannedCount = 0
    
    init() {
        self.authorizationStatus = PHPhotoLibrary.authorizationStatus(for: .readWrite)
    }
    
    func requestAccess(completion: @escaping (Bool) -> Void) {
        PHPhotoLibrary.requestAuthorization(for: .readWrite) { status in
            DispatchQueue.main.async {
                self.authorizationStatus = status
                completion(status == .authorized || status == .limited)
            }
        }
    }
    
    func scanLibrary() {
        guard authorizationStatus == .authorized || authorizationStatus == .limited else { return }
        
        isScanning = true
        duplicates = []
        screenshots = []
        largeVideos = []
        scannedCount = 0
        
        DispatchQueue.global(qos: .userInitiated).async {
            let fetchOptions = PHFetchOptions()
            // Fetch everything
            let allAssets = PHAsset.fetchAssets(with: fetchOptions)
            let total = allAssets.count
            
            var screenshotsTemp: [PHAsset] = []
            var videosTemp: [PHAsset] = []
            
            // Metadata fingerprint maps for duplicates: (Dimensions + Duration if video) -> Asset List
            var fingerprintMap: [String: [PHAsset]] = [:]
            
            allAssets.enumerateObjects { (asset, index, stop) in
                // Track progress
                DispatchQueue.main.async {
                    self.scannedCount = index + 1
                }
                
                // 1. Detect Screenshots
                if asset.mediaSubtypes.contains(.photoScreenshot) {
                    screenshotsTemp.append(asset)
                }
                
                // 2. Detect Large Videos (e.g. videos longer than 30s or matching large criteria)
                if asset.mediaType == .video {
                    if asset.duration > 30.0 {
                        videosTemp.append(asset)
                    }
                }
                
                // 3. Generate fingerprint for duplicate detection
                // Using dimensions and duration + creation date rounded to nearest 5 seconds
                let width = asset.pixelWidth
                let height = asset.pixelHeight
                let dateSec = Int(asset.creationDate?.timeIntervalSince1970 ?? 0)
                let dateKey = dateSec / 5 // Round to nearest 5s to catch burst duplicates
                
                let fingerprint = "\(width)x\(height)_\(dateKey)_\(asset.mediaType.rawValue)"
                fingerprintMap[fingerprint, default: []].append(asset)
            }
            
            // Resolve duplicate groups
            var duplicatesTemp: [DuplicateGroup] = []
            
            for (_, assets) in fingerprintMap {
                if assets.count > 1 {
                    // Sort assets by creation date or keep the best one as representative
                    let sortedAssets = assets.sorted { ($0.creationDate ?? Date()) < ($1.creationDate ?? Date()) }
                    let representative = sortedAssets[0]
                    let duplicateList = Array(sortedAssets.dropFirst())
                    
                    // Estimate size based on dimensions (average compress ratios)
                    let estimatedSize = Int64(assets.count - 1) * Int64(representative.pixelWidth * representative.pixelHeight * 3 / 10)
                    
                    duplicatesTemp.append(DuplicateGroup(
                        representativeAsset: representative,
                        duplicates: duplicateList,
                        totalSize: estimatedSize
                    ))
                }
            }
            
            DispatchQueue.main.async {
                self.duplicates = duplicatesTemp.sorted { $0.totalSize > $1.totalSize }
                self.screenshots = screenshotsTemp
                self.largeVideos = videosTemp.sorted { $0.duration > $1.duration }
                self.isScanning = false
            }
        }
    }
    
    func deleteAssets(_ assets: [PHAsset], completion: @escaping (Bool) -> Void) {
        PHPhotoLibrary.shared().performChanges({
            PHAssetChangeRequest.deleteAssets(assets as NSArray)
        }) { success, error in
            DispatchQueue.main.async {
                completion(success)
            }
        }
    }
}
